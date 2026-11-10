"""Statistici zilnice pentru Vatra, scrise în directorul dat (branch-ul `stats`).

- instalări active: din statisticile oficiale Home Assistant (analytics.home-assistant.io),
  adunate peste toate cheile `*_ha_home_brain` (prefixul diferă după adresa repo-ului adăugat);
- trafic GitHub (clonări = instalații HA care au adăugat repo-ul, vizite): API-ul ține doar 14 zile,
  așa că îl adunăm aici zi de zi. Are nevoie de un token cu drept de citire „Administration”
  (secretul TRAFFIC_TOKEN); fără el, partea de trafic se sare.

Vatra însuși nu trimite nimic nicăieri.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SLUG = "_ha_home_brain"
REPO = os.environ.get("GITHUB_REPOSITORY", "RazvanR1/Vatra")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "stats")


def get(url, token=None):
    req = urllib.request.Request(url, headers={"User-Agent": "vatra-stats", "Accept": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def load(name, default):
    p = OUT / name
    return json.loads(p.read_text()) if p.exists() else default


def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def installs():
    data = get("https://analytics.home-assistant.io/addons.json")
    total, versions, keys = 0, {}, {}
    for key, v in data.items():
        if key.endswith(SLUG):
            total += int(v.get("total", 0))
            keys[key] = int(v.get("total", 0))
            for ver, n in (v.get("versions") or {}).items():
                versions[ver] = versions.get(ver, 0) + int(n)
    return total, dict(sorted(versions.items())), keys


def merge_daily(old, new):
    """Unește seriile zilnice ale GitHub (ultimele 14 zile) cu istoricul păstrat."""
    days = {d["timestamp"][:10]: d for d in old}
    for d in new:
        days[d["timestamp"][:10]] = {"timestamp": d["timestamp"], "count": d["count"], "uniques": d["uniques"]}
    return [days[k] for k in sorted(days)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()

    total, versions, keys = installs()
    history = [h for h in load("installs.json", []) if h["date"] != today]
    history.append({"date": today, "installs": total, "versions": versions, "keys": keys})
    save("installs.json", history)
    print(f"installs: {total} {versions}")

    traffic = load("traffic.json", {"clones": [], "views": []})
    token = os.environ.get("TRAFFIC_TOKEN") or ""
    if token:
        try:
            for kind in ("clones", "views"):
                data = get(f"https://api.github.com/repos/{REPO}/traffic/{kind}", token)
                traffic[kind] = merge_daily(traffic.get(kind, []), data.get(kind, []))
            traffic["referrers"] = get(f"https://api.github.com/repos/{REPO}/traffic/popular/referrers", token)
            traffic["updated"] = today
            save("traffic.json", traffic)
        except Exception as err:  # noqa: BLE001
            print(f"traffic skipped: {err}")
    else:
        print("traffic skipped: no TRAFFIC_TOKEN")

    clones_total = sum(d["uniques"] for d in traffic.get("clones", []))
    views_total = sum(d["uniques"] for d in traffic.get("views", []))

    save("badge-installs.json", {"schemaVersion": 1, "label": "installs", "message": str(total),
                                 "color": "41BDF5", "namedLogo": "homeassistant"})
    summary = {"date": today, "installs": total, "versions": versions,
               "clones_uniques_sum": clones_total, "views_uniques_sum": views_total}
    save("summary.json", summary)
    # Pentru integrarea Scrape din Home Assistant (selectori #installs, #clones, #views).
    (OUT / "summary.html").write_text(
        f'<html><body><span id="installs">{total}</span><span id="clones">{clones_total}</span>'
        f'<span id="views">{views_total}</span><span id="date">{today}</span></body></html>\n')


if __name__ == "__main__":
    main()
