"""Print the CHANGELOG section of a version: `python release_notes.py 2.8.1` -> title line, then body."""
import re
import sys
from pathlib import Path

version = sys.argv[1]
text = Path(__file__).resolve().parents[2].joinpath("ha_home_brain", "CHANGELOG.md").read_text(encoding="utf-8")
m = re.search(rf"^## {re.escape(version)}\b(.*?)$\n(.*?)(?=^## |\Z)", text, re.M | re.S)
if not m:
    print(f"Vatra {version}\n\nSee CHANGELOG.md.")
    sys.exit(0)
title = m.group(1).strip(" –-")
print(f"Vatra {version}" + (f" – {title}" if title else ""))
print()
print(m.group(2).strip())
print("\n---\nUpdate from **Settings → Apps → Vatra**. Full history: [CHANGELOG](https://github.com/RazvanR1/Vatra/blob/main/ha_home_brain/CHANGELOG.md)")
