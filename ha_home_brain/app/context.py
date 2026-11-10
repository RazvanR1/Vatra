"""Contextul casei: ce entități țin de același dispozitiv, ce dispozitive sunt „în repaus”
și ce consumatori mari funcționează acum. Folosit ca să nu confundăm o stare normală cu o defecțiune."""
from __future__ import annotations

import logging
import re
from collections import defaultdict

from .i18n import t

log = logging.getLogger("home_brain.context")

DOWN = ("unavailable", "unknown", None)

# Trei trepte, de la cea mai blândă la cea mai gravă. Doar ultima ajunge pe telefon.
UNUSUAL = "unusual"   # statistic neobișnuit, dar explicabil / fără efect
ANOMALY = "anomaly"   # posibilă problemă, de verificat în panou
FAULT = "fault"       # defecțiune confirmată: tot dispozitivul a picat, de prea mult timp
def tier_label(tier: str) -> str:
    return t(f"tier.{tier}") if tier in (UNUSUAL, ANOMALY, FAULT) else tier

# Senzori care au sens doar cât dispozitivul lucrează (cartografiere, curățare, progres, ETA...).
TASK_WORDS = re.compile(
    r"(?:^|[._])(?:mapping|cartografiere|cleaning_time|cleaning_area|cleaning_progress|current_clean|"
    r"current_task|current_room|current_map|progress|remaining|remaining_time|eta|task|job|print|cycle|"
    r"program|wash|dry|speed|heading|course|trip|ride|altitude|accuracy|last_seen|signal)(?:$|_)", re.I)
REST_VACUUM = {"docked", "idle", "charging", "paused", "returning", "standby", "sleeping"}
CHARGING_WORDS = re.compile(r"charg|incarc|încărc", re.I)
MOBILE_WORDS = re.compile(r"trotinet|scooter|bike|bicicl|car_|masina|mașin|tracker|gps|phone|telefon|"
                          r"watch|ceas", re.I)

# Consumatori mari: dacă funcționează, un consum mare e explicat.
HEAVY_WORDS = re.compile(r"pompa|pompă|heat_?pump|pdc|centrala|centrală|boiler|aer_?cond|\bac\b|_ac_|"
                         r"cuptor|oven|plita|plită|cooktop|masina_de_spalat|washer|uscator|dryer|"
                         r"dishwasher|vase|incalzire|încălzire|heater|ev_?charg|wallbox|charger", re.I)
ACTIVE_HVAC = {"heating", "cooling", "preheating", "defrosting", "drying", "fan"}
RUNNING_CLASSES = {"running", "power", "heat", "cold", "plug"}
# Relee / prize care alimentează permanent becuri smart: „pornit” nu înseamnă „lumină aprinsă”.
BULB_FEED_WORDS = re.compile(r"bec|becuri|bulb|lumin|light|lamp|veioz|spot|led", re.I)


class HomeContext:
    def __init__(self, ha) -> None:
        self.ha = ha
        self.entity_device: dict[str, str] = {}
        self.device_entities: dict[str, list[str]] = defaultdict(list)

    # ---------- registru ----------
    async def refresh(self) -> None:
        """Citește din HA ce entități aparțin fiecărui dispozitiv."""
        try:
            entries = await self.ha.ws({"type": "config/entity_registry/list"})
        except Exception as err:  # noqa: BLE001
            log.warning("Could not read the entity registry: %s", err)
            return
        self.load(entries or [])

    def load(self, entries: list[dict]) -> None:
        self.entity_device.clear()
        self.device_entities = defaultdict(list)
        for e in entries:
            eid, dev = e.get("entity_id"), e.get("device_id")
            if eid and dev:
                self.entity_device[eid] = dev
                self.device_entities[dev].append(eid)

    def siblings(self, eid: str) -> list[str]:
        dev = self.entity_device.get(eid)
        return [e for e in self.device_entities.get(dev, []) if e != eid] if dev else []

    def _st(self, eid: str) -> dict:
        return self.ha.states.get(eid) or {}

    # ---------- dispozitiv ----------
    def device_alive(self, eid: str) -> bool | None:
        """True dacă alte entități ale aceluiași dispozitiv funcționează; None dacă nu știm."""
        sib = [e for e in self.siblings(eid) if e in self.ha.states]
        if not sib:
            return None
        return any(self._st(e).get("state") not in DOWN for e in sib)

    def at_rest(self, eid: str) -> str | None:
        """Motivul pentru care dispozitivul stă pe loc / se încarcă / nu lucrează, dacă se vede."""
        for e in [eid, *self.siblings(eid)]:
            s = self._st(e)
            state, a = s.get("state"), s.get("attributes", {})
            d = e.split(".", 1)[0]
            dc = a.get("device_class")
            if d == "vacuum" and state in REST_VACUUM:
                return t("ctx.docked", name=self.ha.name(e), state=state)
            if d == "device_tracker" and state == "home":
                return t("ctx.home", name=self.ha.name(e))
            if d == "binary_sensor" and state == "on" and (dc == "battery_charging" or CHARGING_WORDS.search(e)):
                return t("ctx.charging", name=self.ha.name(e))
            if d == "binary_sensor" and state == "off" and dc in ("moving", "motion", "running"):
                return t("ctx.still", name=self.ha.name(e))
            if d == "sensor" and isinstance(state, str) and CHARGING_WORDS.search(e) \
                    and state.lower() in ("charging", "se încarcă", "on", "true", "full", "charged"):
                return t("ctx.state", name=self.ha.name(e), state=state)
        return None

    def expected_down(self, eid: str) -> str | None:
        """Explică de ce e normal ca entitatea să fie indisponibilă sau să nu raporteze."""
        rest = self.at_rest(eid)
        if rest and (TASK_WORDS.search(eid) or MOBILE_WORDS.search(eid)
                     or eid.startswith(("device_tracker.", "vacuum."))):
            return rest
        if rest and self.device_alive(eid):
            return rest
        if TASK_WORDS.search(eid) and self.device_alive(eid):
            return t("ctx.task_sensor")
        return None

    # ---------- energie ----------
    def active_loads(self) -> list[str]:
        """Consumatori mari care funcționează acum (pompa de căldură, centrala, AC...)."""
        out: list[str] = []
        for e, s in self.ha.states.items():
            d = e.split(".", 1)[0]
            a = s.get("attributes", {})
            state = s.get("state")
            name = a.get("friendly_name", e)
            if d == "climate" and (a.get("hvac_action") in ACTIVE_HVAC):
                out.append(f"{name}: {a.get('hvac_action')}")
            elif d == "water_heater" and state not in ("off",) + DOWN:
                out.append(f"{name}: {state}")
            elif d == "binary_sensor" and state == "on" and (
                    a.get("device_class") in RUNNING_CLASSES and HEAVY_WORDS.search(e + " " + str(name))):
                out.append(t("ctx.running", name=name))
            elif d in ("switch", "fan") and state == "on" and HEAVY_WORDS.search(e + " " + str(name)) \
                    and not BULB_FEED_WORDS.search(e):
                out.append(t("ctx.on", name=name))
            elif d == "sensor" and a.get("device_class") == "power" and HEAVY_WORDS.search(e + " " + str(name)):
                try:
                    if float(state) > 300:
                        out.append(f"{name}: {float(state):.0f} W")
                except (TypeError, ValueError):
                    pass
        return out[:12]

    def is_bulb_feed(self, eid: str) -> bool:
        """Releu/priză care ține becurile smart alimentate permanent."""
        d = eid.split(".", 1)[0]
        if d != "switch":
            return False
        name = str(self._st(eid).get("attributes", {}).get("friendly_name", ""))
        return bool(BULB_FEED_WORDS.search(eid + " " + name))

    def related(self, eid: str, limit: int = 4) -> str:
        """Stările entităților-surori, pe scurt, ca context pentru agenți."""
        parts = []
        for e in self.siblings(eid)[:limit]:
            s = self._st(e)
            if s.get("state") in DOWN:
                continue
            unit = s.get("attributes", {}).get("unit_of_measurement", "")
            parts.append(f"{e.split('.', 1)[1]}={s.get('state')}{unit}")
        return ", ".join(parts)


def flaky(transitions: list[tuple], eid: str, min_episodes: int = 3) -> bool:
    """Entitatea trece des prin „unavailable” și își revine singură -> e comportamentul ei normal."""
    episodes, down = 0, False
    for _ts, e, _old, new, _o in transitions:
        if e != eid:
            continue
        if new in ("unavailable", "unknown"):
            down = True
        elif down:
            episodes += 1
            down = False
    return episodes >= min_episodes
