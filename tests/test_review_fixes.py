"""Fixes from the code review in issue #5."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ha_home_brain"))

from app.approvals import Guardrails  # noqa: E402
from app.automations import FollowThermostat, HeatingAcLock  # noqa: E402
from app.ha import ORIGIN_AUTOMATION, ORIGIN_DEVICE, ORIGIN_USER  # noqa: E402
from app.store import Store  # noqa: E402


def test_store_rolls_back_and_keeps_the_data():
    store = Store(":memory:")
    store.add_transition(1.0, "light.a", "off", "on", "user")
    store.add_sample(1.0, "sensor.t", 21.0)
    store.db.execute("DROP TABLE samples")
    with pytest.raises(sqlite3.Error):
        store.flush()
    assert not store.db.in_transaction
    assert store._tr_buf and store._num_buf  # kept for the next flush
    store.add_transitions([(2.0, "light.b", "off", "on", "user")])  # the connection still works
    assert len(store.transitions(0)) == 1


def test_important_device_found_by_its_name():
    g = Guardrails({})
    assert g.evaluate("switch", "turn_off", "switch.plug_01", {}, "Frigider")[0] == "approve"
    assert g.evaluate("switch", "turn_off", "switch.plug_01", {}, "Lampa")[0] == "allowed"
    assert g.evaluate("cover", "set_cover_position", "cover.garage", {"position": 100})[0] == "approve"
    assert g.evaluate("cover", "toggle", "cover.garage", {})[0] == "approve"


class _HA:
    def __init__(self, states):
        self.states = states
        self.calls = []
        self.brain_contexts, self.automation_contexts = set(), {"auto1"}

    def state(self, eid):
        return self.states.get(eid, {}).get("state")

    def attr(self, eid, name, default=None):
        return self.states.get(eid, {}).get("attributes", {}).get(name, default)

    async def call_service(self, domain, service, data=None, target=None):
        self.calls.append((domain, service, data, target))


def test_classify_keeps_people_with_a_parent_context():
    from app.ha import HAClient

    ha = _HA({})
    classify = HAClient.classify.__get__(ha)
    assert classify({"id": "x", "parent_id": "p", "user_id": "u"}) == f"{ORIGIN_USER}:u"
    assert classify({"id": "x", "parent_id": "auto1", "user_id": None}) == ORIGIN_AUTOMATION
    assert classify({"id": "x", "parent_id": "p"}) == ORIGIN_AUTOMATION
    assert classify({"id": "x"}) == ORIGIN_DEVICE


async def test_valve_gets_a_value_it_can_hold():
    ha = _HA({"climate.leader": {"state": "heat", "attributes": {"temperature": 21.3}},
              "climate.trv": {"state": "heat", "attributes": {"temperature": 21.5, "target_temp_step": 0.5}}})
    rule = FollowThermostat(ha, None, {"leader_climate": "climate.leader", "follower_climates": ["climate.trv"]})
    await rule.evaluate()
    assert ha.calls == []  # 21.3 rounds to 21.5, which the valve already has
    ha.states["climate.leader"]["attributes"]["temperature"] = 20.2
    await rule.evaluate()
    assert ha.calls[-1][2] == {"temperature": 20.0}


async def test_boiler_comes_back_after_a_restart():
    store = Store(":memory:")
    ha = _HA({"climate.ac": {"state": "heat"}, "climate.boiler": {"state": "heat"}})
    cfg = {"ac_climates": ["climate.ac"], "boiler_climate": "climate.boiler"}
    await HeatingAcLock(ha, None, cfg, store).evaluate()
    assert ha.calls[-1][2] == {"hvac_mode": "off"}
    ha.states["climate.boiler"]["state"] = "off"
    ha.states["climate.ac"]["state"] = "off"
    restarted = HeatingAcLock(ha, None, cfg, store)
    await restarted.evaluate()
    assert ha.calls[-1][2] == {"hvac_mode": "heat"}
    assert store.get("boiler_saved_mode") is None
