"""Clothing tips (offline) and the rain nowcast / forecast text (needs internet for the last two checks)."""
import sys
sys.path.insert(0, '.')
from app.utils import weather as w
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
check("frost -> winter clothes", "Winterjacke" in w.clothing_tip(-5, 0, 10, 10))
check("cold day", "warme Jacke" in w.clothing_tip(2, 8, 10, 10))
check("mild + rain -> umbrella", "Regenjacke oder Schirm" in w.clothing_tip(10, 14, 80, 10))
check("big swing -> onion look", "Zwiebellook" in w.clothing_tip(8, 22, 10, 10))
check("hot + uv -> sunscreen", "Sonnencreme" in w.clothing_tip(18, 30, 0, 5, 8) and "luftige" in w.clothing_tip(18, 30, 0, 5, 8))
check("storm wind", "windig" in w.clothing_tip(10, 14, 10, 55))
if "--live" in sys.argv:
    text, place = w.weather_text("Hamburg", None, "today")
    check("forecast text has a clothing line", place and "Kleidung:" in text)
    r = w.rain_soon(53.55, 10.0)
    check("rain nowcast answers (None or a dict)", r is None or "in_minutes" in r)
print("ALL OK" if ok else "FAILED")
