"""Costs: what your devices cost in a period you choose, at the price on your real invoices.

Prices come from:
- invoices in **Paperless-ngx** (electricity, gas… any supplier): billing period, quantity and the amount
  with VAT are read from the OCR text – known Romanian layouts by rules, anything else by the AI;
- the **E·ON România** integration (gas): billed amounts and monthly m³, averaged over 12 months,
  because a consumption agreement ("convenție") bills estimates and evens them out later.

Consumption comes from the Energy dashboard's devices (long-term statistics), so any period works,
including a past invoice's period – then Vatra also shows how much of the invoiced kWh your measured
devices explain.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp

from .i18n import t

log = logging.getLogger("home_brain.costs")

RO_MONTHS = ["ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie", "august",
             "septembrie", "octombrie", "noiembrie", "decembrie"]


def ro_num(s: str) -> float | None:
    """'1.856,84' -> 1856.84 ; '446,00' -> 446.0 ; '0.5' -> 0.5"""
    s = (s or "").strip().replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def ro_date(s: str) -> date | None:
    m = re.match(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", s or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


NUM = r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d+|\d+)"


def parse_invoice_text(text: str) -> dict | None:
    """Rules for Romanian utility invoices (Hidroelectrica, and the common 'perioadă de facturare'
    layout). Returns {period_start, period_end, quantity, unit, total, utility} or None."""
    if not text:
        return None
    flat = re.sub(r"[ \t]+", " ", text)
    per = re.search(r"Perioad[aă] de facturare\s*:?\s*(\d{1,2}\.\d{1,2}\.\d{4})\s*[-–]\s*(\d{1,2}\.\d{1,2}\.\d{4})", flat)
    if not per:
        per = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})\s*[-–]\s*(\d{1,2}\.\d{1,2}\.\d{4})", flat)
    qty = re.search(r"Consum[^\n]{0,60}?perioada de facturare\s*" + NUM + r"\s*(kWh|MWh|mc|m3|m³)", flat, re.I)
    if not qty:
        qty = re.search(r"Consum (?:total|facturat)[^\n]{0,40}?" + NUM + r"\s*(kWh|MWh|mc|m3|m³)", flat, re.I)
    no_vat = re.search(r"Valoare facturat[aă] f[aă]r[aă] TVA[^\n]*?" + NUM + r"\s*lei", flat, re.I)
    vat = re.search(r"\bTVA\s*\d+%\s*\([^)]*\)\s*" + NUM + r"\s*lei", flat)
    total = None
    if no_vat and vat:
        total = ro_num(no_vat.group(1)) + ro_num(vat.group(1))
    else:
        m = re.search(r"Total (?:factur[aă] curent[aă]|de plat[aă] factur[aă] curent[aă])[^\n]*?" + NUM + r"\s*lei", flat, re.I)
        total = ro_num(m.group(1)) if m else None
    if not (per and qty and total):
        return None
    unit = qty.group(2).replace("mc", "m³").replace("m3", "m³")
    q = ro_num(qty.group(1))
    if unit == "MWh":
        q, unit = q * 1000, "kWh"
    utility = "electricity" if re.search(r"energie (?:electric|activ)", flat, re.I) else ("gas" if re.search(r"gaz", flat, re.I) else "other")
    return {"period_start": ro_date(per.group(1)).isoformat(), "period_end": ro_date(per.group(2)).isoformat(),
            "quantity": round(q, 3), "unit": unit, "total": round(total, 2), "utility": utility, "parsed_by": "rules"}


def eon_gas(states: dict) -> dict | None:
    """Average gas price from the E·ON România integration: last 12 invoices / consumption."""
    inv_st = next((s for e, s in states.items() if e.startswith("sensor.eonromania_") and e.endswith("_arhiva_facturi")), None)
    if not inv_st:
        return None
    invoices = []
    for k, v in inv_st.get("attributes", {}).items():
        m = re.match(r"Factur[aă] (\w+) (\d{4})", k)
        if m and m.group(1).lower() in RO_MONTHS:
            amount = ro_num(re.match(r"\s*([\d.,]+)", str(v)).group(1)) if re.match(r"\s*[\d.,]+", str(v)) else None
            if amount is not None:
                invoices.append((int(m.group(2)), RO_MONTHS.index(m.group(1).lower()) + 1, amount))
    months: dict[tuple[int, int], float] = {}
    for e, s in states.items():
        m = re.match(r"sensor\.eonromania_.*_arhiva_consum_gaz(?:_(\d{4}))?(?:_\d+)?$", e)
        if not m:
            continue
        year = int(m.group(1)) if m.group(1) else None
        for k, v in s.get("attributes", {}).items():
            mm = re.match(r"Consum lunar (\w+)", k)
            if mm and mm.group(1).lower() in RO_MONTHS and year:
                q = ro_num(re.match(r"\s*([\d.,]+)", str(v)).group(1)) if re.match(r"\s*[\d.,]+", str(v)) else None
                if q is not None:
                    months[(year, RO_MONTHS.index(mm.group(1).lower()) + 1)] = q
    invoices.sort()
    last = invoices[-12:]
    if not last or not months:
        return None
    # Same window for both: the months that have consumption and are covered by the invoices.
    keys = sorted(months)[-len(last):]
    m3 = sum(months[k] for k in keys)
    lei = sum(a for _, _, a in last)
    return {"utility": "gas", "supplier": "E·ON România", "unit": "m³", "total": round(lei, 2),
            "quantity": round(m3, 2), "price": round(lei / m3, 3) if m3 else None,
            "months": [{"month": f"{y}-{mo:02d}", "m3": months[(y, mo)]} for y, mo in sorted(months)],
            "invoices": [{"month": f"{y}-{mo:02d}", "lei": a} for y, mo, a in invoices]}


class Costs:
    def __init__(self, ha, llm, store, tz: ZoneInfo, cfg: dict | None = None) -> None:
        cfg = cfg or {}
        self.ha, self.llm, self.store, self.tz = ha, llm, store, tz
        self.url = (cfg.get("paperless_url") or "").rstrip("/")
        self.token = cfg.get("paperless_token") or ""
        self._last_sync = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.token)

    # ---------- invoices ----------
    async def sync(self, force: bool = False) -> int:
        """Reads new invoices from Paperless (every 6 h, or on demand). Returns how many are new."""
        if not self.enabled or (not force and time.time() - self._last_sync < 6 * 3600):
            return 0
        self._last_sync = time.time()
        known = self.store.get("invoices", {})
        new = 0
        params = {"content__icontains": "perioad", "ordering": "-created", "page_size": "100",
                  "fields": "id,title,created,correspondent,content"}
        try:
            async with aiohttp.ClientSession(headers={"Authorization": f"Token {self.token}"}) as s:
                async with s.get(f"{self.url}/api/documents/", params=params, timeout=aiohttp.ClientTimeout(total=60)) as r:
                    if r.status != 200:
                        log.warning("Paperless answered %s", r.status)
                        return 0
                    docs = (await r.json()).get("results", [])
                corr = {}
                async with s.get(f"{self.url}/api/correspondents/", params={"page_size": "200"}) as r:
                    if r.status == 200:
                        corr = {c["id"]: c["name"] for c in (await r.json()).get("results", [])}
        except Exception as err:  # noqa: BLE001
            log.warning("Paperless unavailable: %s", err)
            return 0
        for d in docs:
            if str(d["id"]) in known:
                continue
            content = d.get("content") or ""
            if not re.search(r"kWh|m3|m³|\bmc\b", content):
                known[str(d["id"])] = None  # not a utility invoice; don't look again
                continue
            inv = parse_invoice_text(content) or await self._ai_parse(content)
            if inv:
                inv.update({"doc_id": d["id"], "title": d.get("title", ""), "supplier": corr.get(d.get("correspondent")) or d.get("title", "")[:40],
                            "price": round(inv["total"] / inv["quantity"], 4) if inv.get("quantity") else None,
                            "url": f"{self.url}/documents/{d['id']}/details"})
                new += 1
            known[str(d["id"])] = inv
        self.store.set("invoices", known)
        if new:
            log.info("Costs: %d new invoices read from Paperless", new)
        return new

    async def _ai_parse(self, content: str) -> dict | None:
        if not getattr(self.llm, "enabled", False):
            return None
        try:
            d, _raw = await self.llm.chat_json([{"role": "system", "content": t("costs.ai_prompt")},
                                                {"role": "user", "content": content[:6000]}], timeout=120)
            d = d or {}
            if not (d.get("period_start") and d.get("period_end") and d.get("quantity") and d.get("total")):
                return None
            return {"period_start": str(d["period_start"])[:10], "period_end": str(d["period_end"])[:10],
                    "quantity": float(d["quantity"]), "unit": d.get("unit", "kWh"), "total": float(d["total"]),
                    "utility": d.get("utility", "other"), "parsed_by": "ai"}
        except Exception as err:  # noqa: BLE001
            log.debug("AI invoice parse failed: %s", err)
            return None

    def invoices(self) -> list[dict]:
        out = [v for v in self.store.get("invoices", {}).values() if v]
        return sorted(out, key=lambda x: x["period_end"], reverse=True)

    def price_for(self, utility: str, start: date, end: date) -> dict | None:
        """The invoice that overlaps the period most; otherwise the most recent one."""
        cands = [i for i in self.invoices() if i.get("utility") == utility and i.get("price")]
        if not cands:
            return None

        def overlap(i):
            a, b = date.fromisoformat(i["period_start"]), date.fromisoformat(i["period_end"])
            return max(0, (min(b, end) - max(a, start)).days)
        best = max(cands, key=lambda i: (overlap(i), i["period_end"]))
        return best

    # ---------- consumption ----------
    async def devices(self) -> list[dict]:
        try:
            prefs = await self.ha.ws({"type": "energy/get_prefs"}) or {}
        except Exception:  # noqa: BLE001
            return []
        return [{"stat": d["stat_consumption"], "name": d.get("name") or self.ha.name(d["stat_consumption"])}
                for d in prefs.get("device_consumption", []) if d.get("stat_consumption")]

    async def kwh(self, stat: str, start: datetime, end: datetime) -> float | None:
        try:
            r = await self.ha.ws({"type": "recorder/statistic_during_period", "statistic_id": stat,
                                  "fixed_period": {"start_time": start.isoformat(), "end_time": end.isoformat()},
                                  "types": ["change"]})
            v = (r or {}).get("change")
            return round(float(v), 3) if v is not None else None
        except Exception as err:  # noqa: BLE001
            log.debug("Statistic %s unavailable: %s", stat, err)
            return None

    async def period(self, start: date, end: date) -> dict:
        """Cost of every measured device between start and end (end inclusive)."""
        s = datetime.combine(start, datetime.min.time(), self.tz)
        e = datetime.combine(end + timedelta(days=1), datetime.min.time(), self.tz)
        price = self.price_for("electricity", start, end)
        rows = []
        for d in await self.devices():
            k = await self.kwh(d["stat"], s, e)
            if k is None or k <= 0:
                continue
            rows.append({"name": d["name"], "entity_id": d["stat"], "kwh": k,
                         "lei": round(k * price["price"], 2) if price else None})
        rows.sort(key=lambda r: -r["kwh"])
        total_kwh = round(sum(r["kwh"] for r in rows), 2)
        out = {"start": start.isoformat(), "end": end.isoformat(), "devices": rows, "kwh": total_kwh,
               "lei": round(total_kwh * price["price"], 2) if price else None, "price": price}
        # Same period as an invoice: how much of the invoiced energy do the measured devices explain?
        if price and price["period_start"] == out["start"] and price["period_end"] == out["end"]:
            out["invoice_kwh"] = price["quantity"]
            out["covered"] = round(100 * total_kwh / price["quantity"]) if price["quantity"] else None
        out["gas"] = self.gas_period(start, end)
        return out

    def gas_period(self, start: date, end: date) -> dict | None:
        g = eon_gas(self.ha.states)
        if not g or not g.get("price"):
            return None
        m3 = 0.0
        for m in g["months"]:
            y, mo = map(int, m["month"].split("-"))
            first = date(y, mo, 1)
            nxt = date(y + (mo == 12), mo % 12 + 1, 1)
            days = (nxt - first).days
            ov = (min(end + timedelta(days=1), nxt) - max(start, first)).days
            if ov > 0:
                m3 += m["m3"] * ov / days       # monthly data: spread evenly over the days
        return {"m3": round(m3, 2), "lei": round(m3 * g["price"], 2), "price": g["price"], "supplier": g["supplier"],
                "months": g["months"][-12:], "invoices": g["invoices"][-12:]}

    def summary_line(self) -> str:
        """For Jarvis: the prices Vatra knows."""
        parts = []
        el = next((i for i in self.invoices() if i.get("utility") == "electricity"), None)
        if el:
            parts.append(t("costs.ctx_el", price=f"{el['price']:.2f}", supplier=el["supplier"],
                           start=el["period_start"], end=el["period_end"]))
        g = eon_gas(self.ha.states)
        if g and g.get("price"):
            parts.append(t("costs.ctx_gas", price=f"{g['price']:.2f}"))
        return "; ".join(parts)
