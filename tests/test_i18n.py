"""2.1: English and Romanian. One language per installation, `auto` follows Home Assistant."""
from __future__ import annotations

import re
import string
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ha_home_brain"))

from app import i18n  # noqa: E402
from app.i18n import S, t  # noqa: E402
from app.guard import Guard  # noqa: E402
from app.notify import Notifier  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "ha_home_brain"
RO_CHARS = re.compile(r"[ăâîșțĂÂÎȘȚ]")


def test_every_entry_has_both_languages_with_same_placeholders():
    fmt = string.Formatter()
    for key, e in S.items():
        assert set(e) == {"en", "ro"}, key
        ph = [{f for _, f, _, _ in fmt.parse(e[lang]) if f} for lang in ("en", "ro")]
        assert ph[0] == ph[1], f"{key}: {ph}"
        assert not RO_CHARS.search(e["en"]), f"Romanian text in English for {key}"


def test_resolve_auto_follows_ha_language():
    assert i18n.resolve("auto", "ro") == "ro"
    assert i18n.resolve("auto", "en-GB") == "en"
    assert i18n.resolve("auto", "de") == "en"      # limbi fără traducere -> engleză
    assert i18n.resolve("auto", None) == "en"
    assert i18n.resolve("ro", "en") == "ro"        # opțiunea explicită câștigă
    assert i18n.resolve("en", "ro") == "en"


def test_missing_key_never_crashes():
    i18n.set_language("en")
    assert t("does.not.exist") == "does.not.exist"


def test_all_used_keys_exist():
    used = set()
    for f in (ROOT / "app").glob("*.py"):
        if f.name == "i18n.py":
            continue
        used |= set(re.findall(r"""\b(?:t|tr)\(\s*["']([a-z_]+\.[a-z0-9_.]+|[a-z_]+)["']""", f.read_text()))
    dynamic = {k for k in used if k.endswith(".")}
    assert not (used - dynamic - set(S)), used - dynamic - set(S)
    for k in ("climate", "energy", "security", "server"):
        assert f"agent.{k}.name" in S and f"agent.{k}.task" in S
    for d in ("weekday", "weekend", "all"):
        assert f"hab.days.{d}" in S


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


async def test_guard_notification_in_english():
    i18n.set_language("en")
    from datetime import datetime, timedelta, timezone
    ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    ha = HA([{"entity_id": "sensor.fridge", "state": "unavailable", "attributes": {"friendly_name": "Fridge"},
              "last_changed": ago, "last_updated": ago}])
    n = Notifier(ha, ["notify.mobile_app_x"], cfg={"quiet_hours": "0-0"}, tz=ZoneInfo("UTC"))
    await Guard(ha, n, {}, None, None).run_once()
    title, msg = ha.calls[0][2]["title"], ha.calls[0][2]["message"]
    assert title == "Device unavailable" and msg.startswith("Fridge has been unavailable for 120 minutes")


def test_agent_prompt_language_switches():
    from app.agents import ClimateAgent
    i18n.set_language("en")
    assert ClimateAgent().name == "Climate" and "Answer in English" in t("agent.prompt", name="x", site="",
                                                                        task="", actions="")
    i18n.set_language("ro")
    assert ClimateAgent().name == "Climă" and "Răspunzi în română" in t("agent.prompt", name="x", site="",
                                                                        task="", actions="")


def test_panel_has_both_languages():
    html = (ROOT / "app" / "static" / "index.html").read_text()
    block = html[html.index("const L = {"):html.index("let LANG")]
    en = set(re.findall(r'"([^"]+)":', block[block.index("en:"):block.index("ro:")]))
    ro = set(re.findall(r'"([^"]+)":', block[block.index("ro:"):]))
    assert en == ro and len(en) > 50
    for key in re.findall(r'data-i18n="([^"]+)"', html):
        assert key in en, key


def test_config_has_language_option():
    cfg = (ROOT / "config.yaml").read_text()
    assert "language: auto" in cfg and "language: list(auto|en|ro)" in cfg
