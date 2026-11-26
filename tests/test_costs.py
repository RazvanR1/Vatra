"""Costs: invoice parsing (Hidroelectrica layout, E·ON integration) and device cost per period."""
import asyncio
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ha_home_brain"))

from app.costs import Costs, eon_gas, parse_invoice_text, ro_num  # noqa: E402

HIDRO = """Factură seria FX nr. 26113994282 din data de 12.11.2026
Produse Valoare
Perioadă de facturare:
04.07.2026 - 23.10.2026 1 Valoare facturată fără TVA (conform "Detalii factură") 426,04 lei
2 Total bază de impozitare TVA (21%) 426,04 lei
Data scadență: 3 TVA 21% (3=2*21%) 89,47 lei
14.12.2026
4 Dobânzi penalizatoare 8,46 lei
5 TOTAL DE PLATĂ FACTURĂ CURENTĂ (5=1+3+4) 523,97 lei
6 Sold Cont Contract la data emiterii facturii (facturi 1.332,87 lei
7 TOTAL DE PLATĂ CONT CONTRACT (7=5+6) 1.856,84 lei
8 Consum Energie Activă în perioada de facturare 446,00 kWh
9 Preţ final contractual 1,16 lei/kWh
"""


def test_ro_numbers():
    assert ro_num("1.856,84") == 1856.84 and ro_num("446,00") == 446.0 and ro_num("12") == 12.0


def test_hidroelectrica_invoice():
    inv = parse_invoice_text(HIDRO)
    assert inv["period_start"] == "2026-07-04" and inv["period_end"] == "2026-10-23"
    assert inv["quantity"] == 446.0 and inv["unit"] == "kWh" and inv["utility"] == "electricity"
    assert inv["total"] == 515.51            # value + VAT; no penalties, no old balance
    assert parse_invoice_text("Confirmare plată 44,37 lei") is None


STATES = {
    "sensor.eonromania_1_arhiva_facturi": {"attributes": {
        "Factură septembrie 2026 (nr. 1)": "85,01 lei", "Factură octombrie 2026 (nr. 2)": "44,37 lei",
        "Factură noiembrie 2026 (nr. 3)": "266,31 lei (neachitată), scadentă pe 14.12.2026", "Facturi emise": 3}},
    "sensor.eonromania_1_arhiva_consum_gaz_2026_2": {"attributes": {
        "Consum lunar septembrie": "22,3 m3", "Consum lunar octombrie": "63,55 m3", "Consum lunar noiembrie": "111,23 m3",
        "Consum mediu zilnic în noiembrie": "3,708 m3"}},
}


def test_eon_gas_average_price():
    g = eon_gas(STATES)
    assert g["quantity"] == 197.08 and g["total"] == 395.69
    assert g["price"] == round(395.69 / 197.08, 3)
    assert [m["month"] for m in g["months"]] == ["2026-09", "2026-10", "2026-11"]


class FakeHA:
    def __init__(self):
        self.states = STATES

    def name(self, e):
        return e

    async def ws(self, msg):
        if msg["type"] == "energy/get_prefs":
            return {"device_consumption": [{"stat_consumption": "sensor.ac", "name": "AC"},
                                           {"stat_consumption": "sensor.boiler", "name": "Boiler"},
                                           {"stat_consumption": "sensor.off", "name": "Unused"}]}
        if msg["type"] == "recorder/statistic_during_period":
            return {"change": {"sensor.ac": 120.0, "sensor.boiler": 30.5, "sensor.off": 0}[msg["statistic_id"]]}


class Store(dict):
    def set(self, k, v): self[k] = v


def test_period_cost_with_invoice_price_and_coverage():
    store = Store(invoices={"7": {**parse_invoice_text(HIDRO), "supplier": "Hidroelectrica", "doc_id": 7,
                                  "price": round(515.51 / 446, 4)}})
    c = Costs(FakeHA(), SimpleNamespace(enabled=False), store, ZoneInfo("Europe/Bucharest"))
    r = asyncio.run(c.period(date(2026, 7, 4), date(2026, 10, 23)))
    assert [d["name"] for d in r["devices"]] == ["AC", "Boiler"]          # unused device left out
    assert r["kwh"] == 150.5 and r["lei"] == round(150.5 * round(515.51 / 446, 4), 2)
    assert r["invoice_kwh"] == 446.0 and r["covered"] == 34
    # Gas for October only: 63.55 m³ at the average price
    g = c.gas_period(date(2026, 10, 1), date(2026, 10, 31))
    assert g["m3"] == 63.55
