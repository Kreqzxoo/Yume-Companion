"""
Fotografiert Webclient (Port 8000) und Dashboard (Port 8765) mit Playwright/Chromium.
Vorher:  take_screenshots.py <Ordner> web   (startet beide Server und wartet)
Aufruf:  python tools/dev/take_web_screenshots.py <Web-Token> [Zielordner]
"""
import os
import re
import sys
from playwright.sync_api import sync_playwright

token = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "..", "..", "docs", "images", "web")
os.makedirs(out, exist_ok=True)

USER = os.environ.get("USERNAME", "benutzer")

CLEAN_JS = r"""
(user) => {
  const re = /[A-Za-z]:\\Users\\[^\\\s]+\\(?:OneDrive\\)?(?:Desktop\\)?(?:[^\\\s]*Projekt\\)?(?:[^\\]*(?:BETA|Yume[^\\]*)\\)?/gi;
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n; while ((n = w.nextNode())) { n.nodeValue = n.nodeValue.replace(re, 'C:\\Yume-Companion\\').replace(new RegExp(user, 'gi'), 'Name'); }
}
"""

PATH_RE = re.compile(r"[A-Za-z]:(?:\\|/)+Users(?:\\|/)+[^\\/\s\"]+(?:\\|/)+(?:OneDrive(?:\\|/)+)?(?:Desktop(?:\\|/)+)?(?:[^\\/\s\"]*Projekt(?:\\|/)+)?(?:[^\\/\"]*(?:BETA|Yume[^\\/\"]*)(?:\\|/)+)?", re.I)


def sanitize(route):
    """Ersetzt Benutzerpfade und Namen in den Antworten des Dashboards, bevor die Seite sie anzeigt."""
    resp = route.fetch()
    body = resp.text()
    body = PATH_RE.sub(lambda m: "C:\\Yume-Companion\\\\", body)
    body = re.sub(re.escape(USER), "Name", body, flags=re.I)
    route.fulfill(response=resp, body=body)


with sync_playwright() as p:
    b = p.chromium.launch()
    # Webclient wie auf dem Handy
    ctx = b.new_context(color_scheme="dark", viewport={"width": 412, "height": 915}, device_scale_factor=2, is_mobile=True)
    page = ctx.new_page()
    page.goto(f"http://127.0.0.1:8000/?token={token}")
    page.wait_for_timeout(5000)
    page.screenshot(path=os.path.join(out, "webclient_handy.png"))
    # Webclient am PC
    ctx2 = b.new_context(color_scheme="dark", viewport={"width": 1280, "height": 800})
    page2 = ctx2.new_page()
    page2.goto(f"http://127.0.0.1:8000/?token={token}")
    page2.wait_for_timeout(5000)
    page2.screenshot(path=os.path.join(out, "webclient_pc.png"))
    # Dashboard
    ctx3 = b.new_context(color_scheme="dark", viewport={"width": 1400, "height": 1000})
    page3 = ctx3.new_page()
    page3.route("**/api/**", sanitize)
    page3.goto("http://127.0.0.1:8765/?token=demo-token")
    page3.wait_for_timeout(6000)
    page3.evaluate(CLEAN_JS, USER)
    page3.screenshot(path=os.path.join(out, "dashboard_oben.png"))
    page3.screenshot(path=os.path.join(out, "dashboard_voll.png"), full_page=True)
    b.close()
print("fertig:", out)
