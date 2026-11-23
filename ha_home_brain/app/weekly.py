"""Raportul săptămânal: duminică seara, un mesaj scurt cu ce a făcut Vatra în ultimele 7 zile."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

from .i18n import t

log = logging.getLogger("home_brain.weekly")
WEEK = 7 * 86400


class WeeklyReport:
    def __init__(self, brain, cfg: dict | None = None) -> None:
        cfg = cfg or {}
        self.brain = brain
        self.enabled = bool(cfg.get("weekly_report", True))
        self.weekday = 6                                   # duminică
        self.hour = int((cfg.get("agents") or {}).get("digest_hour", 19))

    def _since(self, items: list[dict], since: float) -> list[dict]:
        return [i for i in items if (i.get("ts") or 0) >= since]

    def build(self, now: float | None = None) -> dict:
        """Cifrele și rândurile raportului (folosit și de panou)."""
        b = self.brain
        now = now or time.time()
        since = now - WEEK
        store = b.store
        done = self._since(store.items("done", limit=500), since)
        automations = [d for d in done if d.get("automation_id")]
        actions = [d for d in done if not d.get("automation_id") and d.get("kind") != "cleanup"]
        cleaned = [d for d in done if d.get("kind") == "cleanup" and d.get("status") == "done"]
        undone = [d for d in done if d.get("status") == "undone"]
        approvals = self._since(store.items("approval", limit=1000), since)
        findings = [a for a in approvals if a.get("kind") == "finding"]
        insights = [i for i in self._since(store.items("insight", limit=500), since) if i.get("severity") != "info"]
        habits_new = self._since(store.items("habit", ("new", "proposed"), limit=200), since)
        alerts_active = len(b.notifier.active)
        alerts_week = b.notifier.counted("alerts_new") if hasattr(b.notifier, "counted") else 0
        alerts_fixed = b.notifier.counted("alerts_fixed") if hasattr(b.notifier, "counted") else 0
        vac_days = b.vacation.days_in_last(7) if hasattr(b, "vacation") else 0.0
        stats = {"automations": len(automations), "actions": len(actions), "undone": len(undone),
                 "cleaned": sum(len(d.get("entities", [])) for d in cleaned), "findings": len(findings),
                 "insights": len(insights), "habits_new": len(habits_new), "alerts_active": alerts_active,
                 "alerts_week": alerts_week, "alerts_fixed": alerts_fixed, "cleanup_left": len(getattr(b.cleanup, "candidates", []) or []),
                 "vacation_days": round(vac_days, 1)}
        lines = []
        if stats["automations"] or stats["habits_new"]:
            lines.append(t("week.habits", new=stats["habits_new"], created=stats["automations"]))
        if stats["actions"]:
            lines.append(t("week.actions", n=stats["actions"], undone=stats["undone"]))
        lines.append(t("week.alerts", week=stats["alerts_week"], fixed=stats["alerts_fixed"],
                       active=stats["alerts_active"]))
        if stats["findings"] or stats["insights"]:
            lines.append(t("week.observed", findings=stats["findings"], insights=stats["insights"]))
        if stats["cleaned"]:
            lines.append(t("week.cleaned", n=stats["cleaned"]))
        if stats["cleanup_left"]:
            lines.append(t("week.cleanup_left", n=stats["cleanup_left"]))
        if stats["vacation_days"] >= 0.5:
            lines.append(t("week.vacation", days=f"{stats['vacation_days']:.0f}"))
        if insights:
            lines.append(t("week.top", title=insights[0].get("title", "")))
        modes = getattr(b, "modes", None)
        if modes is not None and modes.entities:
            lines += [modes.line(item) for item in modes.summary(now)]
        return {"ts": now, "stats": stats, "lines": lines}

    async def send(self) -> dict:
        report = self.build()
        self.brain.store.set("weekly_report", report)
        await self.brain.notifier.send(t("week.title"), "\n".join(f"• {x}" for x in report["lines"]), "info",
                                       key="weekly")
        self.brain.store.log("memorie", t("week.sent"))
        return report

    async def run_forever(self) -> None:
        if not self.enabled:
            return
        while True:
            await asyncio.sleep(600)
            now = datetime.now(self.brain.tz)
            week = now.strftime("%G-W%V")
            if now.weekday() != self.weekday or now.hour < self.hour or self.brain.store.get("weekly_sent") == week:
                continue
            self.brain.store.set("weekly_sent", week)
            try:
                await self.send()
            except Exception:  # noqa: BLE001
                log.exception("Weekly report failed")


def _iso_ts(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return 0.0
