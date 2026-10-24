"""'Hey Yume' on the PC: wake phrase matching and the state logic with fake events (no microphone, no Whisper). Overlay is built without the 3D view."""
import sys, os, time, asyncio
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, '.')
from types import SimpleNamespace
from PyQt6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from app.utils import pc_wake as pw
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
phr = ["Hey Yume", "Yume"]
for text, want_ok, want_rest in (("Hey Yume wie spät ist es", True, "wie spät ist es"), ("hey jume, mach das Licht an", True, "mach das licht an"), ("Yume", True, ""), ("Hallo Yume!", True, ""),
                                 ("hey yume erzähl was", True, "erzähl was"), ("Yume bist du da", True, "bist du da"), ("ich habe gestern yume gesehen", False, ""),
                                 ("hey du da", False, ""), ("wie spät ist es", False, ""), ("Hey Jule komm her", False, "")):
    got = pw.match_wake(text, phr)
    check(f"{text!r} -> {want_ok}", got[0] == want_ok and (not want_ok or got[1] == want_rest))
# state logic
sent = []
class Fake(pw.PcWake):
    def _send(self, text): sent.append(text)
cfg = {"pcwake_seconds": 25, "pcwake_chime": False, "pcwake_vrm": False}
signals = SimpleNamespace(configuration_settings=SimpleNamespace(get_main_setting=lambda k: cfg.get(k)), current_active_character="Yume",
                          configuration_characters=SimpleNamespace(load_configuration=lambda: {"character_list": {"Yume": {}}}), web_bridge=None, interaction_state="STOPPED")
w = Fake(signals)
w.running = True
w.on_text("wie spät ist es")
check("ignored while asleep", sent == [] and not w.awake)
w.on_text("Hey Yume, erzähl einen Witz")
check("wakes up and sends the rest", w.awake and sent == ["erzähl einen witz"] and w.overlay is not None and w.overlay.isVisible())
w.busy_until = 0
w.on_text("und noch einen")
check("follow-up needs no wake phrase while awake", sent[-1] == "und noch einen")
w.busy_until = time.time() + 10
w.on_text("das ist ihre eigene stimme")
check("ignored while she is speaking (own voice)", sent[-1] == "und noch einen")
w.busy_until = 0
w.signals.stop_generation = lambda: sent.append("STOP")
w.on_text("tschüss")
check("goodbye ends the conversation and stops the answer", not w.awake and sent[-1] == "STOP")
w.on_text("erzähl mir was")
check("asleep again", sent[-1] == "STOP")
w.signals.interaction_state = "LISTENING"
w.on_text("hey yume")
check("paused while the call screen listens", not w.awake)
# bridge events drive the overlay text
w.signals.interaction_state = "STOPPED"
w.on_text("hey yume"); w.busy_until = 0
w._on_bridge_event("chunk")
check("overlay: schreibt", w.overlay.state.text().startswith("schreibt"))
w._on_bridge_event("audio")
check("overlay: spricht + microphone muted", w.overlay.state.text().startswith("spricht") and w.busy_until > time.time())
print("ALL OK" if ok else "FAILED")
