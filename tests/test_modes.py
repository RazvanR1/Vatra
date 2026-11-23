"""Mode monitor: time per mode, flapping and stuck alerts, all without touching the entities."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ha_home_brain"))

from app import i18n  # noqa: E402
from app.modes import ModeWatch, changes, segments, shares  # noqa: E402

TZ = ZoneInfo("Europe/Bucharest")
H, DAY = 3600, 86400
NOW = 1_800_000_000.0


class FakeStore(dict):
    def set(self, k, v): self[k] = v
    def log(self, *a): self.setdefault("_log", []).append(a)


class FakeNotifier:
    def __init__(self): self.sent = []
    async def notify(self, title, message, level="info", key=None): self.sent.append((title, message, key))


def _iso(ts):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _watch(points, current, since):
    states = {"input_select.heating": {"state": current, "last_changed": _iso(since), "attributes": {"friendly_name": "Heating"}}}
    ha = SimpleNamespace(states=states, name=lambda e: "Heating")
    w = ModeWatch(ha, FakeStore(), FakeNotifier(), TZ, {"entities": ["input_select.heating"]})
    w.points["input_select.heating"] = points
    w._fetched = NOW + 10 ** 6  # no HA history fetch in tests
    return w


def _normal_days(days=10):
    """Every day: eco 0-6, gas 6-8, hybrid 8-18, eco 18-24 (4 changes a day, never flapping)."""
    pts = []
    for d in range(days, 0, -1):
        base = NOW - d * DAY
        pts += [(base, "eco"), (base + 6 * H, "gas"), (base + 8 * H, "hybrid"), (base + 18 * H, "eco")]
    return pts


def test_segments_shares_and_changes():
    pts = [(0, "eco"), (100, "gas"), (160, "unavailable"), (200, "eco")]
    segs = segments(pts, 300)
    assert shares(segs, 0, 300) == {"eco": 200, "gas": 60}
    assert changes(pts, 0, 300) == 2           # eco->gas, gas->eco (unavailable is not a mode)


def test_summary_time_per_mode():
    w = _watch(_normal_days(), "eco", NOW - DAY + 18 * H)
    week = w.summary(NOW)[0]["week"]
    assert round(week["hybrid"] / H) == 70 and round(week["gas"] / H) == 14
    i18n.set_language("en")
    assert w.line(w.summary(NOW)[0]).startswith("Heating: eco 50% · hybrid 42% · gas 8%")


def test_flapping_alert_once_per_hour():
    pts = _normal_days() + [(NOW - 50 * 60 + i * 300, "eco" if i % 2 else "hybrid") for i in range(9)]
    w = _watch(pts, pts[-1][1], pts[-1][0])
    found = asyncio.run(w.check(NOW))
    assert [f["key"].split(":")[0] for f in found] == ["mode_flap"]
    asyncio.run(w.check(NOW))
    assert len(w.notifier.sent) == 1          # not repeated within the same hour


def test_stuck_alert_when_much_longer_than_ever():
    pts = _normal_days() + [(NOW - 20 * H, "gas")]   # gas usually lasts 2 h, now 20 h
    w = _watch(pts, "gas", NOW - 20 * H)
    found = asyncio.run(w.check(NOW))
    assert [f["key"].split(":")[0] for f in found] == ["mode_stuck"]
    assert "20h00" in found[0]["message"] and "2h00" in found[0]["message"]


def test_normal_day_and_new_entity_stay_quiet():
    w = _watch(_normal_days(), "hybrid", NOW - 2 * H)
    assert asyncio.run(w.check(NOW)) == []
    w = _watch(_normal_days(2), "gas", NOW - 20 * H)   # only 2 days of history: no judgement yet
    assert asyncio.run(w.check(NOW)) == []
