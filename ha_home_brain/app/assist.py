"""Anunță Vatra în Home Assistant (Supervisor discovery), ca integrarea Vatra pentru Assist
să se configureze singură: HA afișează „Vatra descoperit” și un singur buton de confirmare."""
from __future__ import annotations

import logging

log = logging.getLogger("home_brain.assist")


class AssistDiscovery:
    def __init__(self, brain, supervisor) -> None:
        self.brain = brain
        self.supervisor = supervisor
        self.hostname = ""
        self.announced = False

    def token(self) -> str:
        store = self.brain.store
        tok = store.get("assist_token")
        if not tok:
            import secrets
            tok = secrets.token_urlsafe(24)
            store.set("assist_token", tok)
        return tok

    async def announce(self) -> bool:
        if self.supervisor is None or not self.supervisor.available:
            return False
        try:
            info = await self.supervisor.info()
            self.hostname = info.get("hostname") or ""
            if not self.hostname:
                return False
            await self.supervisor._call("POST", "/discovery", {  # noqa: SLF001
                "service": "vatra",
                "config": {"host": self.hostname, "port": 8099, "token": self.token()}})
            self.announced = True
            log.info("Announced to Home Assistant for Assist (%s:8099)", self.hostname)
            return True
        except Exception as err:  # noqa: BLE001
            log.info("Assist discovery not sent: %s", err)
            return False
