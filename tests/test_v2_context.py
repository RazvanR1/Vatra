"""V2: context înainte de alarmă și notificări mai puține. Cazurile vin din casa reală."""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ha_home_brain"))

from app.anomaly import Baselines, Detector  # noqa: E402
from app.context import ANOMALY, FAULT, HomeContext, flaky  # noqa: E402
from app.guard import Guard  # noqa: E402
from app.notify import Notifier, in_quiet  # noqa: E402

TZ = ZoneInfo("Europe/Bucharest")


def ago(hours):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def s(eid, state, hours=2, **attrs):
    return {"entity_id": eid, "state": state, "attributes": attrs, "last_changed": ago(hours),
            "last_updated": ago(hours), "last_reported": ago(hours)}


class HA:
    def __init__(self, states):
        self.states = {x["entity_id"]: x for x in states}
        self.calls = []

    def state(self, e):
        return (self.states.get(e) or {}).get("state")

    def attr(self, e, n, d=None):
        return (self.states.get(e) or {}).get("attributes", {}).get(n, d)

    def name(self, e):
        return self.attr(e, "friendly_name", e)

    async def call_service(self, domain, service, data=None, target=None):
        self.calls.append((domain, service, data))


def ctx_for(ha, devices):
    c = HomeContext(ha)
    c.load([{"entity_id": e, "device_id": d} for d, es in devices.items() for e in es])
    return c


def guard(ha, c):
    n = Notifier(ha, ["notify.mobile_app_razvan"], cfg={"quiet_hours": "0-0"}, tz=TZ)
    g = Guard(ha, n, {"unavailable_minutes": 30}, None, c)
    return g, n


# ---------- 1. false anomalii ----------
def test_scooter_gps_at_home_charging_is_not_a_fault():
    ha = HA([
        s("sensor.trotineta_gps_speed", "unavailable", friendly_name="Trotinetă viteză"),
        s("device_tracker.trotineta", "home", friendly_name="Trotinetă"),
        s("binary_sensor.trotineta_charging", "on", device_class="battery_charging"),
    ])
    c = ctx_for(ha, {"t": ["sensor.trotineta_gps_speed", "device_tracker.trotineta",
                           "binary_sensor.trotineta_charging"]})
    g, _ = guard(ha, c)
    assert g.check() == {}
    assert "sensor.trotineta_gps_speed" in g.explained


def test_vacuum_mapping_time_unavailable_while_docked():
    ha = HA([
        s("sensor.d30_ultra_mapping_time", "unavailable"),
        s("vacuum.d30_ultra", "docked", friendly_name="D30 Ultra"),
        s("sensor.d30_ultra_battery", "100", device_class="battery"),
    ])
    c = ctx_for(ha, {"v": ["sensor.d30_ultra_mapping_time", "vacuum.d30_ultra", "sensor.d30_ultra_battery"]})
    g, _ = guard(ha, c)
    assert g.check() == {}


def test_single_sensor_down_but_device_alive_is_anomaly_not_pushed():
    ha = HA([s("sensor.releu_temp", "unavailable", friendly_name="Releu temp"),
             s("switch.releu", "on", friendly_name="Releu")])
    c = ctx_for(ha, {"r": ["sensor.releu_temp", "switch.releu"]})
    g, n = guard(ha, c)
    found = g.check()
    assert found["unavailable:sensor.releu_temp"].tier == ANOMALY


async def test_whole_device_down_is_confirmed_fault_and_pushed():
    ha = HA([s("sensor.frigider_temp", "unavailable", friendly_name="Frigider temp"),
             s("switch.frigider", "unavailable", friendly_name="Frigider")])
    c = ctx_for(ha, {"f": ["sensor.frigider_temp", "switch.frigider"]})
    g, n = guard(ha, c)
    found = g.check()
    assert {a.tier for a in found.values()} == {FAULT}
    await g.run_once()
    assert len([x for x in ha.calls if x[0] == "notify"]) == 1  # 2 entități, un singur mesaj


async def test_anomaly_only_device_is_not_pushed():
    ha = HA([s("sensor.releu_temp", "unavailable"), s("switch.releu", "on")])
    g, n = guard(ha, ctx_for(ha, {"r": ["sensor.releu_temp", "switch.releu"]}))
    await g.run_once()
    assert ha.calls == [] and "unavailable:sensor.releu_temp" in n.active


def test_flaky_entities_learned_from_history():
    tr = []
    t = time.time() - 20 * 86400
    for i in range(4):
        tr += [(t + i * 3600, "sensor.x", "1", "unavailable", "device"),
               (t + i * 3600 + 600, "sensor.x", "unavailable", "2", "device")]
    assert flaky(tr, "sensor.x") and not flaky(tr, "sensor.y")
    ha = HA([s("sensor.x", "unavailable")])
    g, _ = guard(ha, None)
    g.learn_patterns(tr)
    assert g.check() == {}


def test_silent_gps_skipped_when_at_rest():
    ha = HA([s("sensor.trotineta_latitude", "46.1", hours=12, unit_of_measurement="°"),
             s("device_tracker.trotineta", "home")])
    c = ctx_for(ha, {"t": ["sensor.trotineta_latitude", "device_tracker.trotineta"]})
    d = Detector(ha, {}, TZ, [], c)
    d.base = Baselines(TZ)
    d.base.rate["sensor.trotineta_latitude"] = 6
    d.base.coverage["sensor.trotineta_latitude"] = 1
    assert d._silent("sensor.trotineta_latitude", ha.states["sensor.trotineta_latitude"], time.time()) is None
    ha.states["device_tracker.trotineta"]["state"] = "not_home"
    assert d._silent("sensor.trotineta_latitude", ha.states["sensor.trotineta_latitude"], time.time())


# ---------- 2. context energetic ----------
def _power_detector(ha, c):
    d = Detector(ha, {"min_days": 1}, TZ, [], c)
    d.base = Baselines(TZ)
    hod = datetime.now(TZ).hour
    d.base.hourly[("sensor.consum_casa", hod)] = (50, 400.0, 50.0, 200.0, 900.0, 10)
    d.base.overall["sensor.consum_casa"] = (150.0, 2500.0)
    return d


def test_high_power_explained_by_running_heat_pump():
    ha = HA([s("sensor.consum_casa", "3200", device_class="power", unit_of_measurement="W"),
             s("climate.pompa_caldura", "heat", hvac_action="heating", friendly_name="Pompa de căldură")])
    c = ctx_for(ha, {})
    d = _power_detector(ha, c)
    assert d._range("sensor.consum_casa", ha.states["sensor.consum_casa"], time.time()) is None
    ha.states["climate.pompa_caldura"]["attributes"]["hvac_action"] = "idle"
    assert d._range("sensor.consum_casa", ha.states["sensor.consum_casa"], time.time()) is not None


def test_bulb_feed_relay_on_for_days_is_normal():
    ha = HA([s("switch.releu_becuri_living", "on", hours=200)])
    c = ctx_for(ha, {})
    d = Detector(ha, {}, TZ, [], c)
    d.base = Baselines(TZ)
    d.base.dwell[("switch.releu_becuri_living", "on")] = [3600.0] * 10
    assert d._dwell("switch.releu_becuri_living", ha.states["switch.releu_becuri_living"], time.time()) is None
    assert c.is_bulb_feed("switch.releu_becuri_living")


# ---------- 4/5. notificări ----------
async def test_warnings_are_grouped_and_capped():
    ha = HA([])
    n = Notifier(ha, ["notify.mobile_app_razvan"], cfg={"quiet_hours": "0-0", "max_per_day": 2,
                                                        "batch_minutes": 60}, tz=TZ)
    await n.notify("A", "a", "warning")          # primul pleacă
    for x in "bcde":
        await n.notify(x, x, "warning")           # se strâng
    assert len(ha.calls) == 1 and len(n.queue) == 4
    n.last_batch = 0
    await n.flush()
    assert len(ha.calls) == 2 and "4 lucruri" in ha.calls[-1][2]["title"]
    await n.notify("F", "f", "warning")
    n.last_batch = 0
    await n.flush()
    assert len(ha.calls) == 2                     # plafonul de 2/zi atins -> doar panou
    await n.notify("Apă!", "scurgere", "critical")
    assert len(ha.calls) == 3                     # criticul trece mereu
    assert ha.calls[-1][2]["data"]["priority"] == "high"


async def test_quiet_hours_defer_approvals_and_info_stays_in_panel():
    ha = HA([])
    n = Notifier(ha, ["notify.mobile_app_razvan"], cfg={"quiet_hours": "0-24"}, tz=TZ)
    assert in_quiet("22-7", 23) and in_quiet("22-7", 3) and not in_quiet("22-7", 12)
    await n.request("Obicei nou", "?", {"actions": []}, key="r1")
    await n.notify("Rezolvat", "ok", "info")
    assert ha.calls == [] and len(n.deferred) == 1
    n.quiet = "0-0"
    await n.flush()
    assert len(ha.calls) == 1 and ha.calls[0][2]["data"]["tag"] == "vatra_r1"


async def test_panel_url_in_every_mobile_notification():
    ha = HA([])
    n = Notifier(ha, ["notify.mobile_app_razvan"], cfg={"panel_url": "/abc123_ha_home_brain"}, tz=TZ)
    await n.send("x", "y", "warning")
    data = ha.calls[0][2]["data"]
    assert data["url"] == data["clickAction"] == "/abc123_ha_home_brain"


async def test_cooldown_after_resolve():
    ha = HA([])
    n = Notifier(ha, ["notify.mobile_app_razvan"], cfg={"quiet_hours": "0-0"}, tz=TZ)
    from app.notify import Alert
    await n.raise_alert(Alert("unavailable:x", "t", "m"))
    await n.resolve("unavailable:x", "ok")
    await n.raise_alert(Alert("unavailable:x", "t", "m"))
    assert len(ha.calls) == 1
