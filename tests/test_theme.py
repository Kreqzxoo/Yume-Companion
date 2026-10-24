"""Tests: Yume look (style filter, icon set, renamed texts, links)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.gui import yume_theme as y

bad = []


def check(name, ok):
    print(("OK   " if ok else "FAIL ") + name)
    if not ok:
        bad.append(name)


s = "background: rgb(26, 26, 34); color: #E0E0E0; border: 1px solid rgba(255,255,255,0.1); border-radius: 15px; border: 2px solid #3B82F6;"
a = y.filter_qss(s)
check("old blue / grey colours are replaced", "#3B82F6" not in a.upper() and "#E0E0E0" not in a.upper())
check("white glass becomes lavender glass", "rgba(226,214,255,0.1)" in a)
check("cold black becomes plum", "rgb(31, 23, 48)" in a)
check("corner radii are left alone", "border-radius: 15px" in a)
check("filter is idempotent", y.filter_qss(a) == a)
check("appended text is filtered, the old part is not touched twice", y.filter_qss(a + " color: #A0A0A0;").count("#A99BC4") == 1)
check("empty / non-text input passes", y.filter_qss("") == "" and y.filter_qss(None) is None)

icons = ROOT / "app" / "gui" / "icons"
check("icon set exists and was redrawn", (icons / "main.png").exists() and (ROOT / "tools" / "dev" / "icons_original" / "main.png").exists()
      and (icons / "main.png").read_bytes() != (ROOT / "tools" / "dev" / "icons_original" / "main.png").read_bytes())
check("brand logos were kept", (icons / "openai.png").read_bytes() == (ROOT / "tools" / "dev" / "icons_original" / "openai.png").read_bytes()
      if (ROOT / "tools" / "dev" / "icons_original" / "openai.png").exists() else True)

import yaml
for lang in ("de", "en", "ru"):
    d = yaml.safe_load((ROOT / "app" / "translations" / f"{lang}.yaml").read_text(encoding="utf-8"))
    texts = " ".join(str(v) for v in d.values())
    check(f"{lang}: no 'Soul Stage' / 'Soul Memory' left in the visible texts", "Soul Stage" not in texts and "Soul Memory" not in texts)

b = json.loads((ROOT / "app" / "configuration" / "branding.json").read_text(encoding="utf-8-sig"))
check("no link to the original project's site or donations", all(not b.get(k) for k in ("website_url", "docs_url", "support_url", "discord_url", "github_url", "youtube_url", "author_url")))
check("the original author stays credited", "jofizcd" in b.get("additional_credits", "") and "GPL" in b.get("additional_credits", ""))
check("NOTICE keeps the original copyright", "jofizcd" in (ROOT / "NOTICE.md").read_text(encoding="utf-8") and (ROOT / "LICENSE").exists())

print("\nFEHLER: " + ", ".join(bad) if bad else "\nAlles in Ordnung.")
sys.exit(1 if bad else 0)
