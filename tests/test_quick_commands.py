import sys; sys.path.insert(0,'.')
from app.utils.quick_commands import detect
tests = [
 ("bitte stoppe die musik", True, "pause"), ("mach die musik aus", True, "pause"), ("pause", True, "pause"), ("stopp", False, None),
 ("musik an", True, "resume"), ("spiel weiter", True, "resume"), ("mach die musik wieder an", True, "resume"), ("weiter", True, "resume"),
 ("nächster song", True, "next"), ("skip", True, "next"), ("überspring den song", True, "next"), ("vorheriger titel", True, "previous"),
 ("was läuft gerade?", True, "now"), ("lauter", True, "volume_rel"), ("mach die musik leiser", True, "volume_rel"), ("musik lautstärke 30", True, "volume"),
 ("spiel last christmas", True, None), ("stopp die musik auf dem pc", True, None), ("wie war dein tag", True, None),
 ("öffne whatsapp", True, "open_app"), ("kannst du mir bitte spotify öffnen", True, "open_app"), ("öffne mir instagram auf dem handy", True, "open_app"),
 ("öffne den ordner downloads am pc", True, None), ("taschenlampe an", True, "flashlight"), ("mach die taschenlampe aus", True, "flashlight"),
 ("ich habe die Musik gestern gehört und die war toll", True, None), ("erzähl mir was über die musik von queen", True, None),
]
bad=0
for text, phone, want in tests:
    c = detect(text, phone_turn=phone, phone_connected=True, spotify_connected=True)
    got = c["action"] if c else None
    flag = "ok " if got==want else "BAD"
    if got!=want: bad+=1
    print(flag, repr(text), "->", got, (c or {}).get("params",""))
# phone commands must not trigger in PC chat
print("PC chat open_app:", detect("öffne whatsapp", phone_turn=False, phone_connected=True, spotify_connected=True))
print("bad:", bad)
