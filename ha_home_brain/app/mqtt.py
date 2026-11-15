"""Entitățile Vatra în Home Assistant, prin MQTT discovery.

Publicăm prin serviciul `mqtt.publish` din Home Assistant, deci merge cu orice broker are configurat HA
(Mosquitto sau extern), fără parole. Dacă HA n-are MQTT, modulul stă liniștit: restul Vatra merge la fel.
"""
from __future__ import annotations

import asyncio
import json
import logging

from .i18n import t

log = logging.getLogger("home_brain.mqtt")

PREFIX = "homeassistant"
BASE = "vatra"
STATUS = f"{BASE}/status"
STATE = f"{BASE}/state"
ATTRS = f"{BASE}/alerts"


def entity_configs(version: str) -> list[tuple[str, dict]]:
    """(topic de discovery, payload) pentru fiecare entitate Vatra."""
    device = {"identifiers": ["vatra"], "name": "Vatra", "manufacturer": "RazvanR1",
              "model": "Vatra add-on", "sw_version": version}
    common = {"availability_topic": STATUS, "device": device, "state_topic": STATE}
    items = [
        ("sensor", "active_alerts", {"name": t("mqtt.alerts"), "icon": "mdi:alert-circle-outline",
                                     "value_template": "{{ value_json.alerts }}", "state_class": "measurement",
                                     "json_attributes_topic": ATTRS}),
        ("sensor", "pending_approvals", {"name": t("mqtt.approvals"), "icon": "mdi:account-check-outline",
                                         "value_template": "{{ value_json.approvals }}",
                                         "state_class": "measurement"}),
        ("binary_sensor", "problem", {"name": t("mqtt.problem"), "device_class": "problem",
                                      "value_template": "{{ 'ON' if value_json.problem else 'OFF' }}"}),
        ("sensor", "last_alert", {"name": t("mqtt.last_alert"), "icon": "mdi:message-alert-outline",
                                  "value_template": "{{ value_json.last_alert }}"}),
        ("sensor", "unusual", {"name": t("mqtt.unusual"), "icon": "mdi:chart-bell-curve",
                               "value_template": "{{ value_json.unusual }}", "state_class": "measurement"}),
        ("binary_sensor", "vacation", {"name": t("mqtt.vacation"), "icon": "mdi:bag-suitcase",
                                       "value_template": "{{ 'ON' if value_json.vacation else 'OFF' }}"}),
        ("sensor", "cleanup", {"name": t("mqtt.cleanup"), "icon": "mdi:broom",
                               "value_template": "{{ value_json.cleanup }}", "state_class": "measurement"}),
    ]
    out = []
    for comp, key, cfg in items:
        uid = f"vatra_{key}"
        payload = {**common, **cfg, "unique_id": uid, "default_entity_id": f"{comp}.{uid}"}
        out.append((f"{PREFIX}/{comp}/vatra/{key}/config", payload))
    return out


def snapshot(brain) -> tuple[dict, dict]:
    """Starea curentă (pentru senzori) și atributele (lista alertelor)."""
    active = list(brain.notifier.active.values())
    faults = [a for a in active if a.tier in ("fault", "")]
    last = max(active, key=lambda a: a.time, default=None)
    state = {"alerts": len(active), "approvals": len(brain.approvals.pending()),
             "problem": bool(faults), "last_alert": (last.title if last else t("mqtt.none"))[:250],
             "unusual": len(getattr(brain, "findings", {}) or {}),
             "cleanup": len(getattr(getattr(brain, "cleanup", None), "candidates", []) or []),
             "vacation": bool(getattr(brain, "vacation", None) and brain.vacation.is_active())}
    attrs = {"alerts": [{"title": a.title, "message": a.message, "entity": a.key.partition(":")[2],
                         "level": a.level} for a in sorted(active, key=lambda a: a.time, reverse=True)[:20]]}
    return state, attrs


class MQTTBridge:
    """Publică prin serviciul `mqtt.publish` al Home Assistant: merge cu orice broker are HA, fără parole."""

    REPUBLISH = 60          # secunde: starea se retrimite periodic ...
    EXPIRE = 300            # ... iar dacă Vatra se oprește, entitățile devin „indisponibile” după atât
    DISCOVERY_EVERY = 1800  # retrimitem și configurația (de ex. după o repornire HA)

    def __init__(self, brain, supervisor, version: str, enabled: bool = True) -> None:
        self.brain = brain
        self.supervisor = supervisor
        self.version = version
        self.enabled = enabled
        self.connected = False
        self.error = ""

    async def _publish(self, topic: str, payload, retain: bool = True) -> None:
        if not isinstance(payload, str):
            payload = json.dumps(payload, ensure_ascii=False)
        await self.brain.ha.call_service("mqtt", "publish", {"topic": topic, "payload": payload, "retain": retain})

    async def _has_mqtt(self) -> bool:
        try:
            services = await self.brain.ha.ws({"type": "get_services"})
        except Exception as err:  # noqa: BLE001
            self.error = f"{type(err).__name__}: {err}"
            return False
        if "publish" not in (services or {}).get("mqtt", {}):
            self.error = "MQTT integration is not set up in Home Assistant"
            return False
        return True

    async def publish_discovery(self) -> None:
        if self.version in ("", "dev") and self.supervisor is not None and self.supervisor.available:
            try:
                self.version = (await self.supervisor.info()).get("version") or self.version
            except Exception:  # noqa: BLE001
                pass
        for topic, payload in entity_configs(self.version or "dev"):
            if payload.get("state_topic") == STATE:
                payload = {**payload, "expire_after": self.EXPIRE}
            await self._publish(topic, payload)
        await self._publish(STATUS, "online")

    async def run_forever(self) -> None:
        if not self.enabled:
            return
        delay = 30
        while True:
            await self.brain.ha.connected.wait()
            if not await self._has_mqtt():
                self.connected = False
                log.info("MQTT entities not available: %s (checking again in %ss)", self.error, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 1800)
                continue
            try:
                await self.publish_discovery()
                self.connected, self.error, delay = True, "", 30
                log.info("MQTT: Vatra entities published through Home Assistant")
                last, sent_at, disc_at = None, 0.0, asyncio.get_running_loop().time()
                while self.brain.ha.connected.is_set():
                    now = asyncio.get_running_loop().time()
                    if now - disc_at > self.DISCOVERY_EVERY:
                        await self.publish_discovery()
                        disc_at = now
                    state, attrs = snapshot(self.brain)
                    current = (json.dumps(state, ensure_ascii=False), json.dumps(attrs, ensure_ascii=False))
                    if current != last or now - sent_at >= self.REPUBLISH:
                        await self._publish(STATE, current[0])
                        await self._publish(ATTRS, current[1])
                        last, sent_at = current, now
                    await asyncio.sleep(15)
                self.connected = False  # HA s-a deconectat: la revenire retrimitem tot
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                self.connected, self.error = False, f"{type(err).__name__}: {err}"
                log.warning("MQTT: %s (retrying in %ss)", self.error, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 600)
