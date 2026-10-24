"""Scene recognition for Home Assistant scenes (no Home Assistant needed: the scene list is given)."""
import sys
sys.path.insert(0, '.')
from app.utils.ha_scenes import pick
scenes = [("scene.filmabend", "Filmabend"), ("scene.gute_laune", "Gute Laune"), ("scene.lesen", "Lesen"), ("scene.alles_aus", "Alles aus"), ("scene.tv_ambilight", "TV Ambilight")]
ok = True
def check(text, want):
    global ok
    got = pick(text, scenes)
    good = (got[0] if got else None) == want
    ok &= good
    print(("ok  " if good else "BAD ") + repr(text), "->", got and got[1])
check("Filmabend", "scene.filmabend")
check("aktiviere Filmabend", "scene.filmabend")
check("mach bitte die Szene Gute Laune an", "scene.gute_laune")
check("starte Lesen", "scene.lesen")
check("schalte alles aus", "scene.alles_aus")
check("TV Ambilight an", "scene.tv_ambilight")
check("erzähl mir was über einen Filmabend mit Freunden morgen", None)
check("wie war dein Tag", None)
check("lesen ist toll weil man viel lernt", None)
print("ALL OK" if ok else "FAILED")
