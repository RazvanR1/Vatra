"""Paznicul: verifică periodic sănătatea Home Assistant."""
from __future__ import annotations

import asyncio
import fnmatch
import logging
import time
from datetime import datetime, timezone

from .context import ANOMALY, FAULT, flaky
from .i18n import t
from .notify import Alert

log = logging.getLogger("home_brain.guard")

# media_player lipsește intenționat: televizoarele apar „unavailable” când sunt stinse.
DEFAULT_DOMAINS = ["sensor", "binary_sensor", "switch", "light", "climate", "lock",
                   "cover", "fan", "camera", "alarm_control_panel", "vacuum"]
SUMMARY_AFTER = 3  # peste atâtea alerte noi într-o rundă -> un singur mesaj rezumat


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


class Guard:
    def __init__(self, ha, notifier, cfg: dict, store=None, context=None) -> None:
        self.ha = ha
        self.context = context
        self.flaky_cache: set[str] = set()   # entități care pică și își revin singure, des
        self.notifier = notifier
        self.store = store
        # Când am văzut ultima oară fiecare entitate funcționând. Nu ne bazăm pe last_changed din HA,
        # pentru că la o repornire HA îl resetează și tot ce era deja picat ar părea „proaspăt”.
        self.last_ok: dict[str, float] = (store.get("guard_last_ok", {}) if store else {}) or {}
        if store:
            for key in store.get("guard_active", []) or []:
                notifier.active.setdefault(key, Alert(
                    key=key, message="", title={"unavailable": t("guard.unavailable"),
                                                "battery": t("guard.battery")}.get(key.split(":")[0], t("guard.alert"))))
        self.unavailable_minutes = int(cfg.get("unavailable_minutes", 30))
        # Ce e picat de mai mult de atât e „cunoscut” (dispozitiv scos, container șters) -> nu alertăm.
        self.max_hours = float(cfg.get("max_unavailable_hours", 24))
        self.bad_states = set(cfg.get("bad_states") or ["unavailable"])
        self.domains = set(cfg.get("domains") or DEFAULT_DOMAINS)
        self.battery_threshold = int(cfg.get("battery_threshold", 20))
        self.ignore = [p for p in cfg.get("ignore", []) if p]
        self.interval = int(cfg.get("interval_seconds", 60))
        self.findings: dict[str, Alert] = {}
        self.explained: dict[str, str] = {}  # ce e indisponibil dar normal, și de ce (pentru panou)

    def learn_patterns(self, transitions: list[tuple]) -> None:
        """Din istoricul de 30 de zile: ce entități trec des prin „unavailable” și își revin singure."""
        eids = {t[1] for t in transitions if t[3] in ("unavailable", "unknown")}
        self.flaky_cache = {e for e in eids if flaky(transitions, e)}

    def classify_down(self, eid: str) -> tuple[str | None, str]:
        """(treaptă, explicație). Treaptă None = e normal, nu alertăm deloc."""
        if eid in self.flaky_cache:
            return None, t("ctx.flaky")
        if self.context is None:
            return FAULT, ""
        why = self.context.expected_down(eid)
        if why:
            return None, why
        alive = self.context.device_alive(eid)
        if alive:
            return ANOMALY, t("ctx.device_alive")
        return FAULT, ""

    def ignored(self, entity_id: str) -> bool:
        return any(fnmatch.fnmatch(entity_id, p) for p in self.ignore)

    def battery_level(self, eid: str, st: dict) -> float | None:
        attrs = st.get("attributes", {})
        domain = eid.split(".", 1)[0]
        if domain == "sensor" and attrs.get("device_class") == "battery":
            raw = st.get("state")
        elif "battery_level" in attrs:
            raw = attrs.get("battery_level")
        elif "battery" in attrs and domain != "sensor":
            raw = attrs.get("battery")
        else:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def check(self, now: datetime | None = None) -> dict[str, Alert]:
        """Întoarce problemele curente (cheie -> alertă). Logică pură, ușor de testat."""
        now = now or datetime.now(timezone.utc)
        found: dict[str, Alert] = {}
        for eid, st in self.ha.states.items():
            if self.ignored(eid):
                continue
            domain = eid.split(".", 1)[0]
            name = st.get("attributes", {}).get("friendly_name", eid)
            state = st.get("state")

            if domain in self.domains and state not in self.bad_states and state is not None:
                self.last_ok[eid] = now.timestamp()
            if domain in self.domains and state in self.bad_states:
                since = _parse(st.get("last_changed"))
                seen_ok = self.last_ok.get(eid)
                if self.store is not None and since and seen_ok:
                    since = max(since, datetime.fromtimestamp(seen_ok, timezone.utc))
                recent_ok = self.store is None or (
                    seen_ok is not None and now.timestamp() - seen_ok <= self.max_hours * 3600)
                if since and recent_ok:
                    age = (now - since).total_seconds()
                    if self.unavailable_minutes * 60 <= age <= self.max_hours * 3600:
                        tier, why = self.classify_down(eid)
                        if tier is None:
                            self.explained[eid] = why
                        else:
                            self.explained.pop(eid, None)
                            found[f"unavailable:{eid}"] = Alert(
                                key=f"unavailable:{eid}",
                                title=t("guard.unavailable") if tier == FAULT else t("guard.no_value"),
                                message=t("guard.down_msg", name=name, state=state, minutes=int(age // 60))
                                        + (f" ({why})." if why else "."),
                                tier=tier)
            elif eid in self.explained:
                self.explained.pop(eid, None)

            level = self.battery_level(eid, st)
            if level is not None and level <= self.battery_threshold:
                found[f"battery:{eid}"] = Alert(
                    key=f"battery:{eid}", title=t("guard.battery"),
                    message=t("guard.battery_msg", name=name, level=f"{level:.0f}"),
                    level="warning", tier=FAULT if level <= 5 else ANOMALY)
        return found

    def group(self, alerts: list) -> dict[str, tuple[str, list]]:
        """Alertele grupate pe dispozitiv (sau integrare), în ordinea apariției."""
        out: dict[str, tuple[str, list]] = {}
        for a in alerts:
            eid = a.key.partition(":")[2]
            if self.context is not None and hasattr(self.context, "group_of"):
                gkey, label = self.context.group_of(eid)
            else:
                gkey, label = f"entity:{eid}", self.ha.attr(eid, "friendly_name", eid)
            out.setdefault(gkey, (label, []))[1].append(a)
        return out

    def short_name(self, alert, label: str) -> str:
        """Numele entității fără prefixul dispozitivului („Dishwasher Bosch - Connected” -> „Connected”)."""
        eid = alert.key.partition(":")[2]
        name = str(self.ha.attr(eid, "friendly_name", eid))
        if label and name.lower().startswith(label.lower()):
            name = name[len(label):].lstrip(" -–:·") or name
        return name

    def describe(self, key: str) -> str:
        """Text pentru o alertă activă care nu mai are mesaj (refăcută după repornire)."""
        kind, _, eid = key.partition(":")
        st = self.ha.states.get(eid) or {}
        name = st.get("attributes", {}).get("friendly_name", eid)
        if kind == "battery":
            level = self.battery_level(eid, st) if st else None
            return t("guard.battery_msg", name=name, level=f"{level:.0f}" if level is not None else "?")
        return f"{name}: {st.get('state', '?')}."

    def fixed(self, key: str) -> bool:
        """O alertă activă se închide doar când problema chiar a dispărut."""
        kind, _, eid = key.partition(":")
        st = self.ha.states.get(eid)
        if st is None:
            return True  # entitatea a fost ștearsă
        if kind == "unavailable":
            return st.get("state") not in self.bad_states or self.classify_down(eid)[0] is None
        if kind == "battery":
            level = self.battery_level(eid, st)
            return level is None or level > self.battery_threshold
        return False

    async def run_once(self) -> None:
        found = self.check()
        new = [a for k, a in found.items() if k not in self.notifier.active]
        # Doar defecțiunile confirmate ajung pe telefon (și acelea grupate de Notifier);
        # „posibilele anomalii” rămân în panou.
        push = [a for a in new if a.tier in (FAULT, "")]
        for alert in new:
            await self.notifier.raise_alert(alert, send=False)
        groups = self.group(push)
        if len(groups) == 1 and len(push) > 1:
            # Mai multe entități ale aceluiași dispozitiv / aceleiași integrări: un singur mesaj, pe nume.
            (_, (label, alerts)), = groups.items()
            names = ", ".join(self.short_name(a, label) for a in alerts[:6])
            more = t("guard.and_more", n=len(alerts) - 6) if len(alerts) > 6 else ""
            await self.notifier.notify(t("guard.group_title", name=label),
                                       t("guard.group_msg", count=len(alerts), names=names, more=more),
                                       "warning", key="guard_burst")
        elif len(push) > SUMMARY_AFTER or any(len(v[1]) > 1 for v in groups.values()):
            parts = [t("guard.group_count", name=label, count=len(alerts)) if len(alerts) > 1 else label
                     for label, alerts in groups.values()]
            more = t("guard.and_more", n=len(parts) - 8) if len(parts) > 8 else ""
            await self.notifier.notify(t("guard.burst_title"),
                                       t("guard.burst_msg", count=len(push), names=", ".join(parts[:8]), more=more),
                                       "warning", key="guard_burst")
        else:
            for alert in push:
                if time.time() - self.notifier.recently_resolved.get(alert.key, 0) < self.notifier.cooldown:
                    continue  # tocmai s-a rezolvat și a picat iar: nu insistăm
                await self.notifier.notify(alert.title, alert.message, alert.level, key=alert.key)
        for key in list(self.notifier.active):
            if key.split(":", 1)[0] not in {"unavailable", "battery"}:
                continue
            eid = key.split(":", 1)[1]
            if key in found:
                # Alertă deja activă (de ex. refăcută după o repornire, fără text): îi actualizăm detaliile.
                cur, fresh = self.notifier.active[key], found[key]
                cur.title, cur.message, cur.tier = fresh.title, fresh.message, fresh.tier
                continue
            if self.ignored(eid):
                # Entitatea a fost trecută între timp la „ignoră”: închidem alerta fără mesaj.
                self.notifier.active.pop(key, None)
                continue
            if self.fixed(key):
                name = self.ha.attr(eid, "friendly_name", eid)
                await self.notifier.resolve(key, t("guard.ok_again", name=name))
            elif not self.notifier.active[key].message:
                self.notifier.active[key].message = self.describe(key)
        self.findings = found
        if self.store is not None:
            self.store.set("guard_last_ok", self.last_ok)
            self.store.set("guard_active", sorted(self.notifier.active))

    async def run_forever(self) -> None:
        await self.ha.connected.wait()
        await asyncio.sleep(10)  # lăsăm HA să se stabilizeze după conectare
        while True:
            await self.ha.connected.wait()
            try:
                await self.run_once()
            except Exception:  # noqa: BLE001
                log.exception("Guard check failed")
            await asyncio.sleep(self.interval)
