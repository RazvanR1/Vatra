"""Jarvis: the house state is ordered oldest change first, so the AI server can reuse its prompt cache."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ha_home_brain"))

from app.assistant import Assistant  # noqa: E402


def _st(state, updated, name):
    return {"state": state, "last_updated": updated, "attributes": {"friendly_name": name}}


def _assistant(states):
    llm = SimpleNamespace(enabled=True, model="m", budget_chars=lambda share: 100000)
    return Assistant(SimpleNamespace(states=states), llm, {})


def test_oldest_change_first_so_only_the_tail_differs():
    states = {
        "person.a": _st("home", "2026-11-22T20:00:00+00:00", "A"),
        "light.hall": _st("off", "2026-11-01T10:00:00+00:00", "Hall"),
        "switch.pump": _st("on", "2026-11-20T08:00:00+00:00", "Pump"),
    }
    first = _assistant(states).house_context().splitlines()
    assert [line.split(" | ")[0] for line in first] == ["light.hall", "switch.pump", "person.a"]
    # The pump changes: everything before it stays byte-identical, it moves to the end.
    states["switch.pump"] = _st("off", "2026-11-22T21:00:00+00:00", "Pump")
    second = _assistant(states).house_context().splitlines()
    assert second[:2] == [first[0], first[2]] and second[2].startswith("switch.pump")
