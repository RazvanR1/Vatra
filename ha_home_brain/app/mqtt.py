"""Entitățile Vatra în Home Assistant, prin MQTT discovery.

Brokerul (de obicei add-on-ul Mosquitto) e luat automat de la Supervisor (`services: mqtt:want`).
Dacă nu există broker, modulul stă liniștit: restul Vatra merge la fel.
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
             "cleanup": len(getattr(getattr(brain, "cleanup", None), "candidates", []) or [])}
    attrs = {"alerts": [{"title": a.title, "message": a.message, "entity": a.key.partition(":")[2],
                         "level": a.level} for a in sorted(active, key=lambda a: a.time, reverse=True)[:20]]}
    return state, attrs


class MQTTBridge:
    def __init__(self, brain, supervisor, version: str, enabled: bool = True) -> None:
        self.brain = brain
        self.supervisor = supervisor
        self.version = version
        self.enabled = enabled
        self.connected = False
        self.error = ""

    async def credentials(self) -> dict | None:
        if not self.supervisor.available:
            self.error = "no Supervisor"
            return None
        try:
            if self.version in ("", "dev"):
                self.version = (await self.supervisor.info()).get("version") or self.version
            creds = await self.supervisor.service("mqtt")
            self.error = ""
            return creds
        except Exception as err:  # noqa: BLE001
            self.error = f"{type(err).__name__}: {err}"
            return None

    async def run_forever(self) -> None:
        if not self.enabled:
            return
        try:
            import aiomqtt  # noqa: PLC0415
        except ImportError:
            log.info("aiomqtt not installed; MQTT entities disabled")
            return
        await self.brain.ha.connected.wait()
        delay = 10
        while True:
            creds = await self.credentials()
            if not creds or not creds.get("host"):
                self.connected = False
                self.error = self.error or "no MQTT broker"
                log.info("MQTT entities not available: %s (checking again in %ss)", self.error, delay)
                await asyncio.sleep(delay)  # fără broker: verificăm tot mai rar, poate îl instalezi mai târziu
                delay = min(delay * 2, 900)
                continue
            try:
                will = aiomqtt.Will(STATUS, "offline", retain=True)
                async with aiomqtt.Client(hostname=creds["host"], port=int(creds.get("port", 1883)),
                                          username=creds.get("username"), password=creds.get("password"),
                                          identifier="vatra", will=will) as client:
                    self.connected, self.error, delay = True, "", 10
                    log.info("MQTT connected to %s:%s – Vatra entities published", creds["host"], creds.get("port"))
                    for topic, payload in entity_configs(self.version):
                        await client.publish(topic, json.dumps(payload, ensure_ascii=False), retain=True)
                    await client.publish(STATUS, "online", retain=True)
                    last = None
                    while True:
                        state, attrs = snapshot(self.brain)
                        current = (json.dumps(state, ensure_ascii=False), json.dumps(attrs, ensure_ascii=False))
                        if current != last:
                            await client.publish(STATE, current[0], retain=True)
                            await client.publish(ATTRS, current[1], retain=True)
                            last = current
                        await asyncio.sleep(15)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                self.connected, self.error = False, str(err)
                log.warning("MQTT: %s (retrying in %ss)", err, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 300)
