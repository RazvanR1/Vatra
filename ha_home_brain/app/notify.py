"""Trimiterea alertelor: servicii notify din HA și/sau ntfy, cu o politică anti-spam.

Reguli (V2):
- „critical” pleacă imediat, mereu.
- „warning” nu pleacă pe loc: se strânge și pleacă într-un singur mesaj grupat
  cel mult o dată la `batch_minutes`, în afara orelor de liniște, până la `max_per_day`.
- „info” (rezolvări, mesaje de stare) rămâne doar în panou, dacă nu ceri altfel.
- Aceeași problemă nu se mai trimite din nou timp de `cooldown_hours` după ce s-a rezolvat.
- Cererile de aprobare (cu butoane) pleacă individual, dar așteaptă dimineața în orele de liniște.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, tzinfo
from zoneinfo import ZoneInfo

import aiohttp

log = logging.getLogger("home_brain.notify")


@dataclass
class Alert:
    key: str
    title: str
    message: str
    level: str = "warning"  # info | warning | critical
    time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    resolved: bool = False
    tier: str = ""          # unusual | anomaly | fault (gol = nespecificat)


def in_quiet(spec: str, hour: int) -> bool:
    try:
        a, b = (int(x) for x in str(spec).split("-"))
    except ValueError:
        return False
    if a == b:
        return False
    return (a <= hour or hour < b) if a > b else (a <= hour < b)


class Notifier:
    def __init__(self, ha, services: list[str], ntfy_url: str = "", history: int = 200,
                 cfg: dict | None = None, tz: tzinfo | None = None, store=None) -> None:
        cfg = cfg or {}
        self.ha = ha
        self.services = [s for s in services if s]
        self.ntfy_url = (ntfy_url or "").rstrip("/")
        self.history: deque[Alert] = deque(maxlen=history)
        self.active: dict[str, Alert] = {}
        self.tz = tz or ZoneInfo("Europe/Bucharest")
        self.store = store
        self.mode = cfg.get("mode", "smart")                 # smart | all | critical_only
        self.quiet = cfg.get("quiet_hours", "22-7")
        self.max_per_day = int(cfg.get("max_per_day", 4))
        self.batch_minutes = int(cfg.get("batch_minutes", 120))
        self.send_resolved = bool(cfg.get("send_resolved", False))
        self.cooldown = float(cfg.get("cooldown_hours", 12)) * 3600
        self.queue: list[Alert] = []                          # warning-uri care așteaptă gruparea
        self.deferred: list[tuple[str, str, str, dict | None]] = []  # aprobări amânate (ore de liniște)
        self.last_batch = 0.0
        self.recently_resolved: dict[str, float] = {}
        self.panel_url: str | None = cfg.get("panel_url") or None
        self.sent_log: deque[dict] = deque(maxlen=50)

    # ---------- politică ----------
    def quiet_now(self) -> bool:
        return in_quiet(self.quiet, datetime.now(self.tz).hour)

    def _today(self) -> str:
        return datetime.now(self.tz).date().isoformat()

    def _budget_left(self) -> int:
        used = self.store.get(f"push_count:{self._today()}", 0) if self.store else getattr(self, "_used", 0)
        return self.max_per_day - used

    def _spend(self) -> None:
        if self.store:
            k = f"push_count:{self._today()}"
            self.store.set(k, self.store.get(k, 0) + 1)
        else:
            self._used = getattr(self, "_used", 0) + 1

    # ---------- API folosit de restul aplicației ----------
    async def raise_alert(self, alert: Alert, send: bool = True) -> None:
        """Înregistrează alerta o singură dată per cheie, până se rezolvă; trimiterea respectă politica."""
        if alert.key in self.active:
            return
        self.active[alert.key] = alert
        self.history.appendleft(alert)
        if not send:
            return
        if time.time() - self.recently_resolved.get(alert.key, 0) < self.cooldown and alert.level != "critical":
            log.info("Cooldown, nu retrimit: %s", alert.key)
            return
        await self.notify(alert.title, alert.message, alert.level, key=alert.key)

    async def resolve(self, key: str, message: str | None = None) -> None:
        alert = self.active.pop(key, None)
        if alert is None:
            return
        alert.resolved = True
        self.recently_resolved[key] = time.time()
        self.queue = [a for a in self.queue if a.key != key]  # nu mai anunțăm ce s-a rezolvat deja
        if message:
            ok = Alert(key=key, title=f"Rezolvat: {alert.title}", message=message, level="info")
            ok.resolved = True
            self.history.appendleft(ok)
            if self.send_resolved:
                await self.notify(ok.title, message, "info", key=key)

    async def notify(self, title: str, message: str, level: str = "info", key: str | None = None) -> bool:
        """Mesaj fără butoane, trecut prin politică. Întoarce True dacă a plecat imediat."""
        if level == "critical" or self.mode == "all":
            await self.send(title, message, level, key=key)
            return True
        if self.mode == "critical_only" or level == "info":
            log.info("Doar în panou [%s] %s: %s", level, title, message)
            return False
        self.queue.append(Alert(key=key or title, title=title, message=message, level=level))
        await self.flush()
        return False

    async def request(self, title: str, message: str, data: dict | None, key: str) -> None:
        """Cerere de aprobare cu butoane: pleacă individual, dar nu noaptea."""
        if self.quiet_now():
            self.deferred.append((title, message, key, data))
            return
        await self.send(title, message, "info", data=data, key=key)

    async def flush(self, force: bool = False) -> None:
        if self.quiet_now() and not force:
            return
        if self.deferred:
            items, self.deferred = self.deferred, []
            for title, message, key, data in items:
                await self.send(title, message, "info", data=data, key=key)
        if not self.queue:
            return
        if not force and time.time() - self.last_batch < self.batch_minutes * 60:
            return
        items, self.queue = self.queue, []
        self.last_batch = time.time()
        if self._budget_left() <= 0 and not force:
            log.info("Plafonul zilnic atins; %d mesaje rămân doar în panou", len(items))
            return
        self._spend()
        if len(items) == 1:
            a = items[0]
            await self.send(a.title, a.message, a.level, key=a.key)
            return
        lines = [f"• {a.title}: {a.message}" for a in items[:5]]
        more = f"\n…și încă {len(items) - 5} în panou" if len(items) > 5 else ""
        await self.send(f"Vatra: {len(items)} lucruri de verificat", "\n".join(lines) + more,
                        "warning", key="batch")

    async def run_forever(self) -> None:
        while True:
            await asyncio.sleep(60)
            try:
                await self.flush()
            except Exception:  # noqa: BLE001
                log.exception("Eroare la trimiterea notificărilor grupate")

    # ---------- link către panou ----------
    async def resolve_panel_url(self) -> str:
        """Calea panoului Vatra în HA (ex. /a1b2c3d4_ha_home_brain), ca atingerea notificării să-l deschidă."""
        if self.panel_url:
            return self.panel_url
        slug = None
        token = os.environ.get("SUPERVISOR_TOKEN")
        if token and os.path.exists("/data/options.json"):  # rulăm ca add-on real
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get("http://supervisor/addons/self/info",
                                     headers={"Authorization": f"Bearer {token}"},
                                     timeout=aiohttp.ClientTimeout(total=5)) as r:
                        if r.status == 200:
                            slug = ((await r.json()).get("data") or {}).get("slug")
            except Exception as err:  # noqa: BLE001
                log.debug("Nu am putut afla slug-ul add-on-ului: %s", err)
        if not slug and os.path.exists("/data/options.json") and "-" in os.environ.get("HOSTNAME", ""):
            slug = os.environ["HOSTNAME"].replace("-", "_")
        self.panel_url = f"/{slug}" if slug else "/lovelace"
        return self.panel_url

    def _mobile_data(self, level: str, key: str | None, extra: dict | None) -> dict:
        data: dict = {"group": "vatra", "url": self.panel_url or "/lovelace",
                      "clickAction": self.panel_url or "/lovelace"}
        if key:
            data["tag"] = f"vatra_{key}"[:64]
        if level == "critical":
            data.update({"channel": "Vatra – urgent", "importance": "high", "priority": "high", "ttl": 0,
                         "push": {"interruption-level": "time-sensitive"}})
        else:
            data.update({"channel": "Vatra", "importance": "low" if level == "info" else "default",
                         "push": {"interruption-level": "passive" if level == "info" else "active"}})
        if extra:
            data.update(extra)
        return data

    # ---------- trimitere efectivă ----------
    async def send(self, title: str, message: str, level: str = "info", data: dict | None = None,
                   key: str | None = None) -> None:
        if self.panel_url is None:
            await self.resolve_panel_url()
        self.sent_log.appendleft({"title": title, "level": level, "ts": time.time()})
        for svc in self.services:
            domain, _, name = svc.partition(".")
            if not name:
                domain, name = "notify", domain
            payload = {"title": title, "message": message}
            if name.startswith("mobile_app_"):
                payload["data"] = self._mobile_data(level, key, data)
            try:
                await self.ha.call_service(domain, name, payload)
            except Exception as err:  # noqa: BLE001
                log.warning("Nu am putut trimite prin %s: %s", svc, err)
        if self.ntfy_url:
            prio = {"info": "low", "warning": "default", "critical": "urgent"}.get(level, "default")
            try:
                async with aiohttp.ClientSession() as s:
                    await s.post(self.ntfy_url, data=message.encode(),
                                 headers={"Title": title.encode("utf-8").decode("latin-1", "ignore"),
                                          "Priority": prio, "Tags": "house"})
            except Exception as err:  # noqa: BLE001
                log.warning("Nu am putut trimite pe ntfy: %s", err)
        log.info("[%s] %s: %s", level, title, message)
