"""Mod vacanță: casa e goală mai multe zile.

Pornește singur când toate persoanele sunt plecate de mai mult de `away_hours` (implicit 24), sau manual din panou.
Cât e activ:
- zilele respective nu intră în învățarea obiceiurilor (nu „învățăm” că nu aprinzi nicio lumină);
- observațiile mărunte (lăsat prea mult, senzor tăcut) nu mai apar – casa goală e oricum „neobișnuită”;
- orice mișcare sau ușă/fereastră deschisă în casă ajunge imediat pe telefon.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, tzinfo

from .i18n import t

log = logging.getLogger("home_brain.vacation")

WATCH_CLASSES = {"motion", "occupancy", "presence", "door", "window", "opening", "garage_door"}
QUIET_KINDS = {"dwell", "silent", "flapping"}  # ce nu mai raportăm cât e casa goală


def _ts(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


class Vacation:
    def __init__(self, ha, store, persons: list[str], tz: tzinfo, cfg: dict | None = None) -> None:
        cfg = cfg or {}
        self.ha = ha
        self.store = store
        self.persons = persons
        self.tz = tz
        self.auto = bool(cfg.get("auto", True))
        self.away_hours = float(cfg.get("away_hours", 24))
        self.security_alerts = bool(cfg.get("security_alerts", True))
        self.last_check = time.time()

    # ---------- stare ----------
    @property
    def manual(self) -> str:
        return self.store.get("vacation_manual") or "auto"   # auto | on | off

    def set_manual(self, mode: str) -> None:
        if mode not in ("auto", "on", "off"):
            raise ValueError(mode)
        self.store.set("vacation_manual", mode)
        self.update()

    def last_home(self) -> float | None:
        """Ultima dată când a fost cineva acasă (ținută minte între reporniri)."""
        now = time.time()
        if any(self.ha.state(p) == "home" for p in self.persons):
            self.store.set("vacation_last_home", now)
            return now
        saved = self.store.get("vacation_last_home")
        if saved:
            return saved
        # Prima pornire, toată lumea plecată: cel mai recent moment în care a plecat cineva.
        changes = [_ts((self.ha.states.get(p) or {}).get("last_changed")) for p in self.persons]
        changes = [c for c in changes if c]
        return max(changes) if changes else None

    def is_active(self) -> bool:
        if self.manual == "on":
            return True
        if self.manual == "off" or not self.auto or not self.persons:
            return False
        if any(self.ha.state(p) in (None, "unavailable", "unknown") for p in self.persons):
            return False  # nu știm sigur unde sunt oamenii
        last = self.last_home()
        return last is not None and time.time() - last >= self.away_hours * 3600

    def update(self) -> bool:
        """Ține evidența perioadelor de vacanță (pentru învățare și raport). Întoarce starea curentă."""
        if self.manual == "off" and any(self.ha.state(p) == "home" for p in self.persons):
            self.store.set("vacation_manual", "auto")  # „M-am întors” ține doar până ajunge cineva acasă
        active = self.is_active()
        periods: list[list[float | None]] = self.store.get("vacation_periods", []) or []
        open_period = bool(periods) and periods[-1][1] is None
        now = time.time()
        if active and not open_period:
            start = now if self.manual == "on" else (self.last_home() or now)
            periods.append([start, None])
            self.store.log("memorie", t("vac.started"))
        elif not active and open_period:
            periods[-1][1] = now
            self.store.log("memorie", t("vac.ended", days=f"{(now - periods[-1][0]) / 86400:.1f}"))
        else:
            return active
        self.store.set("vacation_periods", periods[-50:])
        return active

    def periods(self) -> list[tuple[float, float]]:
        now = time.time()
        return [(s, e if e is not None else now) for s, e in (self.store.get("vacation_periods", []) or [])]

    def days(self) -> set[date]:
        """Zilele (locale) atinse de o vacanță – nu le folosim la învățarea obiceiurilor."""
        out: set[date] = set()
        for s, e in self.periods():
            d, end = datetime.fromtimestamp(s, self.tz).date(), datetime.fromtimestamp(e, self.tz).date()
            while d <= end:
                out.add(d)
                d += timedelta(days=1)
        return out

    def days_in_last(self, days: int = 7) -> float:
        since = time.time() - days * 86400
        return sum(max(0.0, e - max(s, since)) for s, e in self.periods() if e > since) / 86400

    # ---------- securitate ----------
    def intrusions(self, recent: list[tuple]) -> list[tuple[str, str]]:
        """(entity_id, nume) pentru mișcare / uși deschise de la ultima verificare, cât e casa goală."""
        since, self.last_check = self.last_check, time.time()
        if not self.security_alerts or not self.is_active():
            return []
        out, seen = [], set()
        for ts, eid, _old, new, *_ in recent:
            if ts <= since or new != "on" or not eid.startswith("binary_sensor.") or eid in seen:
                continue
            dc = (self.ha.states.get(eid) or {}).get("attributes", {}).get("device_class")
            if dc in WATCH_CLASSES:
                seen.add(eid)
                out.append((eid, self.ha.name(eid)))
        return out
