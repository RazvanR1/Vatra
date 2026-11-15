"""Curățenie: dispozitive moarte de mult (vândute, containere șterse, integrări abandonate).

Un dispozitiv e „mort” când toate entitățile lui sunt indisponibile acum ȘI istoricul Home Assistant
arată că n-au avut nicio valoare reală în ultimele `days` zile. Vatra doar propune; cu aprobarea ta
dezactivează entitățile în registrul HA (nu le șterge), iar Anulează le reactivează.
"""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone

from .i18n import t

log = logging.getLogger("home_brain.cleanup")

DEAD = "unavailable"                 # doar „unavailable” înseamnă că dispozitivul nu răspunde
NO_VALUE = {"unavailable", "unknown", "", None}
# Ce nu propunem niciodată: entitățile Vatra însuși și cele de sistem.
SKIP_PREFIXES = ("sensor.vatra_", "binary_sensor.vatra_", "update.", "person.", "zone.", "sun.")
# Entități fără stare: stau normal pe „unknown” până le folosești, deci nu spun nimic despre dispozitiv.
STATELESS = {"button", "input_button", "notify", "scene", "event", "image", "tts", "stt", "conversation",
             "wake_word", "ai_task"}
# Dispozitive care „dorm” normal (televizor oprit, telefon plecat): nu le propunem niciodată.
SLEEPY = {"media_player", "remote", "device_tracker"}


def _sid(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:10]


class Cleanup:
    def __init__(self, ha, store, context, approvals, cfg: dict | None = None) -> None:
        cfg = cfg or {}
        self.ha = ha
        self.store = store
        self.context = context
        self.approvals = approvals
        self.enabled = bool(cfg.get("enabled", True))
        self.days = max(3, int(cfg.get("days", 7)))
        self.max_per_scan = int(cfg.get("max_proposals", 5))
        self.last_scan: float | None = None
        self.candidates: list[dict] = []

    # ---------- detectare ----------
    def dead_now(self) -> list[dict]:
        """Dispozitivele ale căror entități (existente în HA) sunt toate indisponibile acum."""
        out = []
        for dev, eids in self.context.device_entities.items():
            present = [e for e in eids if e in self.ha.states and not e.startswith(SKIP_PREFIXES)]
            if any(e.split(".", 1)[0] in SLEEPY for e in present):
                continue
            live = [e for e in present if e.split(".", 1)[0] not in STATELESS]
            if not live:
                continue
            if all(self.ha.states[e].get("state") == DEAD for e in live):
                out.append({"device_id": dev, "name": self.context.device_name.get(dev) or self.ha.name(live[0]),
                            "entities": sorted(present), "checked": sorted(live)})
        return out

    async def had_value(self, entity_ids: list[str]) -> set[str]:
        """Entitățile care au avut cel puțin o valoare reală în ultimele `days` zile (din istoricul HA)."""
        start = (datetime.now(timezone.utc) - timedelta(days=self.days)).isoformat()
        alive: set[str] = set()
        for i in range(0, len(entity_ids), 50):
            chunk = entity_ids[i:i + 50]
            hist = await self.ha.ws({"type": "history/history_during_period", "start_time": start,
                                     "entity_ids": chunk, "minimal_response": True,
                                     "no_attributes": True, "significant_changes_only": False}, timeout=60)
            hist = hist or {}
            for eid in chunk:
                states = hist.get(eid)
                # Fără niciun istoric (ex. exclusă din recorder) nu putem ști: o considerăm vie.
                if not states or any((s.get("s") if "s" in s else s.get("state")) not in NO_VALUE for s in states):
                    alive.add(eid)
        return alive

    async def scan(self, propose: bool = True) -> list[dict]:
        if not self.enabled:
            return []
        dead = self.dead_now()
        if dead:
            try:
                alive = await self.had_value([e for d in dead for e in d["checked"]])
            except Exception as err:  # noqa: BLE001
                log.warning("Could not read history for cleanup: %s", err)
                return self.candidates
            dead = [d for d in dead if not alive.intersection(d["checked"])]
        dead.sort(key=lambda d: (-len(d["entities"]), d["name"].lower()))
        self.candidates = dead
        self.last_scan = time.time()
        # Propunerile încă în așteptare pentru dispozitive care nu mai sunt moarte se retrag.
        still = {d["device_id"] for d in dead}
        for a in self.approvals.pending():
            if a["kind"] == "cleanup" and a["item_id"] not in still:
                self.store.set_status("approval", a["id"], "resolved")
        if propose:
            sent = 0
            for d in dead:
                if sent >= self.max_per_scan:
                    break
                if await self.propose(d):
                    sent += 1
        if dead:
            self.store.log("memorie", t("cleanup.found", n=len(dead), days=self.days))
        return dead

    async def propose(self, d: dict) -> bool:
        """Cere aprobare în panou (fără notificare). False dacă a mai fost întrebată."""
        existing = self.store.item("approval", _sid("cleanup", d["device_id"]))
        rid_before = existing["status"] if existing else None
        names = ", ".join(self.ha.name(e) for e in d["entities"][:4])
        more = t("guard.and_more", n=len(d["entities"]) - 4) if len(d["entities"]) > 4 else ""
        await self.approvals.ask(
            "cleanup", d["device_id"],
            t("cleanup.title", name=d["name"]),
            t("cleanup.msg", n=len(d["entities"]), days=self.days, names=names, more=more),
            {"device_id": d["device_id"], "name": d["name"], "entities": d["entities"]},
            buttons=[("ok", t("cleanup.btn_disable")), ("no", t("cleanup.btn_keep"))], notify=False)
        return rid_before is None

    # ---------- decizie și anulare ----------
    async def set_disabled(self, entity_ids: list[str], disabled: bool) -> int:
        ok = 0
        for eid in entity_ids:
            try:
                await self.ha.ws({"type": "config/entity_registry/update", "entity_id": eid,
                                  "disabled_by": "user" if disabled else None})
                ok += 1
            except Exception as err:  # noqa: BLE001
                log.warning("Could not %s %s: %s", "disable" if disabled else "enable", eid, err)
        return ok

    async def handle(self, item: dict, decision: str) -> str:
        p = item["payload"]
        if decision != "ok":
            return t("cleanup.kept", name=p["name"])
        n = await self.set_disabled(p["entities"], True)
        did = _sid("done-cleanup", p["device_id"], time.time())
        self.store.put_item("done", did, {"kind": "cleanup", "name": p["name"], "entities": p["entities"],
                                          "device_id": p["device_id"], "service": t("cleanup.done_label", n=n),
                                          "reason": t("cleanup.reason", days=self.days),
                                          "source": "Vatra"}, status="done")
        self.candidates = [c for c in self.candidates if c["device_id"] != p["device_id"]]
        self.store.log("acțiune", t("cleanup.disabled", name=p["name"], n=n))
        return t("cleanup.disabled", name=p["name"], n=n)

    async def undo(self, done: dict) -> str:
        n = await self.set_disabled(done.get("entities", []), False)
        return t("cleanup.enabled", name=done.get("name", ""), n=n)
