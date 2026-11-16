"""Translations: one JSON file per language in app/locales/<code>.json.

Each file has three sections:
  _meta  - {"name": "Magyar", "locale": "hu-HU"}
  app    - notifications, alerts, reports and AI prompts (used here, via t())
  panel  - texts of the web panel (served to the browser by /api/i18n/<code>)

English (en.json) is the reference. Any key missing from another language falls back to
English, then to the key itself, so a partial translation never breaks anything.
A new language needs only a new file: it is picked up automatically (see TRANSLATING.md).

Option `language`: auto | <code>. `auto` follows the Home Assistant language when a file
exists for it, English otherwise.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)
DIR = Path(__file__).parent / "locales"


def _load() -> dict[str, dict]:
    out = {}
    for f in sorted(DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:  # a broken file must not stop the app
            log.warning("Translation %s ignored: %s", f.name, e)
            continue
        out[f.stem.lower()] = {
            "_meta": data.get("_meta") or {},
            "app": {k: v for k, v in (data.get("app") or {}).items() if isinstance(v, str) and v},
            "panel": {k: v for k, v in (data.get("panel") or {}).items() if isinstance(v, str) and v},
        }
    out.setdefault("en", {"_meta": {"name": "English"}, "app": {}, "panel": {}})
    return out


LANGS = _load()
SUPPORTED = tuple(LANGS)
# Compatibility view: S[key][lang] (only the languages that translate the key).
S: dict[str, dict[str, str]] = {}
for _code, _d in LANGS.items():
    for _k, _v in _d["app"].items():
        S.setdefault(_k, {})[_code] = _v

_lang = "en"


def match(lang: str | None) -> str:
    """'hu-HU' -> 'hu' if hu.json exists; unknown -> 'en'."""
    lang = (lang or "en").lower().replace("_", "-")
    if lang in LANGS:
        return lang
    base = lang.split("-")[0]
    return base if base in LANGS else "en"


def set_language(lang: str | None) -> str:
    global _lang
    _lang = match(lang)
    return _lang


def resolve(option: str | None, ha_language: str | None) -> str:
    """Option `language`: an explicit value wins; `auto` uses the HA language."""
    opt = (option or "auto").lower()
    return set_language(ha_language if opt == "auto" else opt)


def lang() -> str:
    return _lang


def languages() -> list[dict]:
    """For the panel: [{code, name, locale, coverage}] — coverage = share of English keys translated."""
    total = len(LANGS["en"]["app"]) + len(LANGS["en"]["panel"]) or 1
    out = []
    for code, d in LANGS.items():
        done = sum(k in d["app"] for k in LANGS["en"]["app"]) + sum(k in d["panel"] for k in LANGS["en"]["panel"])
        out.append({"code": code, "name": d["_meta"].get("name", code), "locale": d["_meta"].get("locale", code),
                    "coverage": round(100 * done / total)})
    return out


def panel(code: str | None) -> dict:
    """Panel texts for a language, completed with English."""
    code = match(code)
    return {**LANGS["en"]["panel"], **LANGS[code]["panel"]}


def t(key: str, **kw) -> str:
    text = LANGS.get(_lang, LANGS["en"])["app"].get(key) or LANGS["en"]["app"].get(key) or key
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError, ValueError):  # bad placeholder in a translation -> use English
            return (LANGS["en"]["app"].get(key) or key).format(**kw)
    return text
