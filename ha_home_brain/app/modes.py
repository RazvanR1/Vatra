"""Mode monitor: watches the "mode" entities of systems you built yourself (an input_select with
eco / hybrid / gas / boost, a select of a heat pump, an alarm mode…) without touching them.

- how long each mode ran today / this week (panel, weekly report, Jarvis)
- an alert when a mode switches much more often than usual (flapping), or when a mode lasts much
  longer than it has ever lasted in the last weeks (stuck)

Vatra only watches: it never changes these entities. The history comes from Home Assistant's
recorder, so the statistics are there from the first start.
"""
from __future__ import annotations

import logging
import statistics
import time
from datetime import datetime, timedelta, timezone

from .i18n import t

log = logging.getLogger("home_brain.modes")
DAY = 86400
HISTORY_DAYS = 14
NON_STATES = {"unavailable", "unknown", "", None}


def segments(points: list[tuple[float, str]], until: float) -> list[tuple[float, float, str]]:
    """[(ts, state)] ordered -> [(start, end, state)], unavailable gaps left out."""
    out = []
    for i, (ts, st) in enumerate(points):
        end = points[i + 1][0] if i + 1 < len(points) else until
        if st not in NON_STATES and end > ts:
            out.append((ts, end, st))
    return out


def shares(segs: list[tuple[float, float, str]], since: float, until: float) -> dict[str, float]:
    """Seconds spent in each state between since and until."""
    out: dict[str, float] = {}
    for a, b, st in segs:
        a, b = max(a, since), min(b, until)
        if b > a:
            out[st] = out.get(st, 0.0) + (b - a)
    return out


def changes(points: list[tuple[float, str]], since: float, until: float) -> int:
    n, prev = 0, None
    for ts, st in points:
        if st in NON_STATES:
            continue
        if prev is not None and st != prev and since <= ts <= until:
            n += 1
        prev = st
    return n


def fmt_dur(sec: float) -> str:
    m = int(round(sec / 60))
    return f"{m // 60}h{m % 60:02d}" if m >= 60 else f"{m} min"


class ModeWatch:
    def __init__(self, ha, store, notifier, tz, cfg: dict | None = None) -> None:
        cfg = cfg or {}
        self.ha, self.store, self.notifier, self.tz = ha, store, notifier, tz
        self.entities: list[str] = [e for e in cfg.get("entities", []) if isinstance(e, str) and "." in e]
        self.alerts = bool(cfg.get("alerts", True))
        self.points: dict[str, list[tuple[float, str]]] = {}
        self._fetched = 0.0

    # ---------- data ----------
    async def refresh(self, force: bool = False) -> None:
        """Mode history from the HA recorder; refreshed hourly (live changes come from the states)."""
        if not self.entities or (not force and time.time() - self._fetched < 3600):
            return
        end = datetime.now(timezone.utc)
        try:
            hist = await self.ha.ws({"type": "history/history_during_period",
                                     "start_time": (end - timedelta(days=HISTORY_DAYS)).isoformat(),
                                     "end_time": end.isoformat(), "entity_ids": self.entities,
                                     "minimal_response": True, "no_attributes": True,
                                     "significant_changes_only": False}, timeout=120) or {}
        except Exception as err:  # noqa: BLE001
            log.warning("Mode history unavailable: %s", err)
            return
        for eid in self.entities:
            pts = []
            for p in hist.get(eid, []):
                ts = _ts(p.get("lc") or p.get("lu") or p.get("last_changed"))
                if ts is not None:
                    pts.append((ts, p.get("s", p.get("state"))))
            self.points[eid] = sorted(pts)
        self._fetched = time.time()

    def on_change(self, eid: str, state: str, ts: float | None = None) -> None:
        if eid in self.entities:
            pts = self.points.setdefault(eid, [])
            if not pts or pts[-1][1] != state:
                pts.append((ts or time.time(), state))

    def _pts(self, eid: str) -> list[tuple[float, str]]:
        pts = list(self.points.get(eid, []))
        st = self.ha.states.get(eid, {}).get("state")
        if st is not None and (not pts or pts[-1][1] != st):
            pts.append((_ts(self.ha.states[eid].get("last_changed")) or time.time(), st))
        return pts

    def _day_start(self, now: float) -> float:
        d = datetime.fromtimestamp(now, self.tz).replace(hour=0, minute=0, second=0, microsecond=0)
        return d.timestamp()

    # ---------- statistics ----------
    def summary(self, now: float | None = None) -> list[dict]:
        now = now or time.time()
        out = []
        for eid in self.entities:
            pts = self._pts(eid)
            segs = segments(pts, now)
            today = shares(segs, self._day_start(now), now)
            week = shares(segs, now - 7 * DAY, now)
            prev = shares(segs, now - 14 * DAY, now - 7 * DAY)
            cur = self.ha.states.get(eid, {})
            out.append({
                "entity_id": eid, "name": self.ha.name(eid), "state": cur.get("state"),
                "since": _ts(cur.get("last_changed")),
                "today": today, "week": week, "prev_week": prev,
                "changes_today": changes(pts, self._day_start(now), now),
                "changes_week": changes(pts, now - 7 * DAY, now),
            })
        return out

    def baseline(self, eid: str, now: float) -> dict:
        """Usual behaviour over the last two weeks, without the last day (which is being judged)."""
        pts = [p for p in self._pts(eid) if p[0] < now - DAY]
        segs = segments(pts, now - DAY)
        longest: dict[str, float] = {}
        count: dict[str, int] = {}
        for a, b, st in segs[1:]:  # the first segment is cut by the history window
            longest[st] = max(longest.get(st, 0.0), b - a)
            count[st] = count.get(st, 0) + 1
        hourly = []
        start = now - HISTORY_DAYS * DAY
        for h in range(int((now - DAY - start) // 3600)):
            hourly.append(changes(pts, start + h * 3600, start + (h + 1) * 3600))
        active = [x for x in hourly if x] or [0]
        p95 = sorted(active)[int(0.95 * (len(active) - 1))]
        return {"longest": longest, "count": count, "hour_p95": p95, "days": len({int(p[0] // DAY) for p in pts})}

    # ---------- alerts ----------
    async def check(self, now: float | None = None) -> list[dict]:
        now = now or time.time()
        await self.refresh()
        found = []
        for eid in self.entities:
            base = self.baseline(eid, now)
            if base["days"] < 3:          # too little history to know what's normal
                continue
            pts = self._pts(eid)
            name = self.ha.name(eid)
            last_hour = changes(pts, now - 3600, now)
            limit = max(4, 2 * base["hour_p95"])
            if last_hour > limit:
                found.append({"key": f"mode_flap:{eid}:{int(now // 3600)}", "entity_id": eid,
                              "title": t("mode.flap_title", name=name),
                              "message": t("mode.flap_msg", name=name, n=last_hour, usual=base["hour_p95"])})
            cur = self.ha.states.get(eid, {})
            st, since = cur.get("state"), _ts(cur.get("last_changed"))
            longest = base["longest"].get(st)
            if since and longest and base["count"].get(st, 0) >= 3 and st not in NON_STATES:
                dur = now - since
                if dur > max(3600, 1.5 * longest):
                    found.append({"key": f"mode_stuck:{eid}:{int(since)}", "entity_id": eid,
                                  "title": t("mode.stuck_title", name=name, state=st),
                                  "message": t("mode.stuck_msg", name=name, state=st, dur=fmt_dur(dur),
                                               longest=fmt_dur(longest))})
        if self.alerts:
            for f in found:
                if self.store.get(f"sent:{f['key']}"):
                    continue
                self.store.set(f"sent:{f['key']}", now)
                self.store.log("modes", f["message"])
                await self.notifier.notify(f["title"], f["message"], "warning", key=f["key"])
        return found

    # ---------- text for the report and Jarvis ----------
    def line(self, item: dict, period: str = "week") -> str:
        data = item[period]
        total = sum(data.values()) or 1
        parts = " · ".join(f"{st} {round(100 * v / total)}%" for st, v in sorted(data.items(), key=lambda x: -x[1]))
        return t("mode.line", name=item["name"], parts=parts or "—",
                 n=item["changes_week" if period == "week" else "changes_today"])

    def context(self) -> str:
        lines = []
        for item in self.summary():
            since = datetime.fromtimestamp(item["since"], self.tz).strftime("%H:%M") if item["since"] else "?"
            today = ", ".join(f"{st} {fmt_dur(v)}" for st, v in sorted(item["today"].items(), key=lambda x: -x[1]))
            lines.append(t("mode.ctx", name=item["name"], state=item["state"], since=since, today=today or "—"))
        return "\n".join(lines)


def _ts(iso) -> float | None:
    if isinstance(iso, (int, float)):
        return float(iso)
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None
