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


def test_every_entry_has_english_and_romanian_with_same_placeholders():
    fmt = string.Formatter()
    for key, e in S.items():
        assert {"en", "ro"} <= set(e), key
        en_ph = {f for _, f, _, _ in fmt.parse(e["en"]) if f}
        for lang, text in e.items():
            assert {f for _, f, _, _ in fmt.parse(text) if f} == en_ph, f"{key} [{lang}]"
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
    en, ro = set(i18n.LANGS["en"]["panel"]), set(i18n.LANGS["ro"]["panel"])
    assert en == ro and len(en) > 50


def test_config_has_language_option():
    cfg = (ROOT / "config.yaml").read_text()
    assert "language: auto" in cfg and "language: list(auto|en|ro" in cfg


# --- 2.7: one file per language (app/locales/<code>.json) ---------------------------------
import json  # noqa: E402

LOCALES = ROOT / "app" / "locales"


def _ph(s):
    return {f for _, f, _, _ in string.Formatter().parse(s) if f}


def test_locale_files_are_consistent_with_english():
    en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    for f in LOCALES.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        assert d.get("_meta", {}).get("name"), f"{f.name}: _meta.name missing"
        for sec in ("app", "panel"):
            extra = set(d.get(sec, {})) - set(en[sec])
            assert not extra, f"{f.name} [{sec}] has keys not in en.json: {extra}"
            for k, v in d.get(sec, {}).items():
                if sec == "app":
                    assert _ph(v) == _ph(en[sec][k]), f"{f.name} {k}: placeholders differ"
                else:
                    assert set(re.findall(r"\{(\w+)\}", v)) == set(re.findall(r"\{(\w+)\}", en[sec][k])), f"{f.name} {k}"


def test_config_language_option_lists_every_locale():
    opt = re.search(r"language: list\(([^)]*)\)", (ROOT / "config.yaml").read_text()).group(1).split("|")
    assert opt[0] == "auto"
    assert {f.stem for f in LOCALES.glob("*.json")} <= set(opt)


def test_panel_keys_exist_in_english():
    html = (ROOT / "app" / "static" / "index.html").read_text()
    used = set(re.findall(r'data-i18n="([^"]+)"', html)) | set(re.findall(r'\bT\("([a-z][\w.]*)"', html))
    missing = {k for k in used if not k.endswith(".")} - set(i18n.LANGS["en"]["panel"])
    assert not missing, missing


def test_fallbacks_and_language_list():
    assert i18n.match("ro-RO") == "ro"
    assert i18n.match("xx-YY") == "en"
    i18n.set_language("ro")
    assert i18n.panel("ro")["tab.overview"] if "tab.overview" in i18n.LANGS["en"]["panel"] else True
    p = i18n.panel("xx")
    assert p == i18n.LANGS["en"]["panel"]
    codes = {x["code"]: x for x in i18n.languages()}
    assert codes["en"]["coverage"] == 100 and "ro" in codes
    i18n.set_language("en")


def test_partial_translation_falls_back_to_english(monkeypatch):
    monkeypatch.setitem(i18n.LANGS, "hu", {"_meta": {"name": "Magyar"}, "app": {}, "panel": {}})
    assert i18n.set_language("hu-HU") == "hu"
    key = next(iter(i18n.LANGS["en"]["app"]))
    assert t(key) == i18n.LANGS["en"]["app"][key]
    i18n.set_language("en")
