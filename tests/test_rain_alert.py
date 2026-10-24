"""Rain alert logic of the organizer loop with a fake phone, fake location and fake forecast (no network)."""
import sys, os, asyncio, tempfile, datetime
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, '.')
from pathlib import Path
from types import SimpleNamespace
from app.utils import routines, commute, weather, organizer
tmp = Path(tempfile.mkdtemp())
organizer.DIR = tmp; routines.FILE = tmp / "r.json"
import app.gui.interface_signals as S
cls = next(v for k, v in vars(S).items() if isinstance(v, type) and hasattr(v, "_rain_check"))
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
sent = []
class FakeBridge:
    def has_phone(self): return True
    async def phone_command(self, action, params, timeout=0):
        sent.append((action, params)); return {"ok": True}
def fake(origin, home, rain, hour=14):
    async def fo(): return origin
    commute.phone_origin = fo
    commute.geocode = lambda text: home
    commute.settings = lambda: {"home": "Zuhause" if home else ""}
    weather.rain_soon = lambda lat, lon, h=70: rain
    me = SimpleNamespace(web_bridge=FakeBridge())
    return me
noon = datetime.datetime.now().replace(hour=14, minute=0)
real_dt = datetime.datetime
class FrozenDT(datetime.datetime):
    @classmethod
    def now(cls, tz=None): return noon
S.datetime.datetime = FrozenDT
away, home = (53.60, 10.10), (53.55, 10.00)
me = fake(away, home, {"in_minutes": 20, "mm": 1.2})
asyncio.run(cls._rain_check(me))
check("alert sent when away from home and rain is coming", len(sent) == 1 and sent[0][0] == "notify" and "20 Minuten" in sent[0][1]["text"])
asyncio.run(cls._rain_check(me))
check("not again within 3 hours", len(sent) == 1)
sent.clear(); me = fake(home, home, {"in_minutes": 20, "mm": 1.2}); asyncio.run(cls._rain_check(me))
check("no alert at home", sent == [])
sent.clear(); me = fake(away, home, None); asyncio.run(cls._rain_check(me))
check("no alert when no rain is coming", sent == [])
cfg = routines.load(); cfg["rain_alert"] = False; routines.save(cfg)
sent.clear(); me = fake(away, home, {"in_minutes": 10, "mm": 0.5}); asyncio.run(cls._rain_check(me))
check("switched off -> nothing", sent == [])
print("ALL OK" if ok else "FAILED")
