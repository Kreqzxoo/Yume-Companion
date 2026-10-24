"""Tests: external tool model (address handling, connection test against a fake server, fallback timer, card builds)."""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.utils import tool_llm as t

bad = []


def check(name, ok):
    print(("OK   " if ok else "FAIL ") + name)
    if not ok:
        bad.append(name)


check("normalize adds http", t.normalize("192.168.1.5:8083/") == "http://192.168.1.5:8083")

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps({"data": [{"id": "Qwen3-8B"}]}).encode())
    def log_message(self, *a): pass

srv = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
ok, text = t.test(f"127.0.0.1:{srv.server_port}")
check("test reaches fake server", ok and "Qwen3-8B" in text)
srv.shutdown()
ok, text = t.test("127.0.0.1:9")
check("test reports unreachable", not ok and "Werkzeuge" in text)
check("empty address", t.test("")[0] is False)

class FakeApi:
    def get_token(self, k): return {"REMOTE_LLM_BASE_URL": "http://192.168.1.50:8080/v1"}.get(k)
t._api = lambda: FakeApi()
check("suggested url = same PC, port 8083", t.suggested_url() == "http://192.168.1.50:8083")

t._settings = lambda: type("S", (), {"get_main_setting": lambda self, k: True if k == "tool_llm_external" else None})()
t.base_url = lambda: "http://x:8083"
check("provider built when on", t.provider() is not None)
t.mark_down(60)
check("provider paused after failure", t.provider() is None)
t._down_until = 0.0

# the card builds without errors (offscreen)
from PyQt6 import QtWidgets, QtGui
app = QtWidgets.QApplication([])
from app.gui import agent_models

class UI:
    translations = {}
    def select_option_tab(self, i): pass
ui = UI(); ui.translations = type("T", (), {"get": staticmethod(lambda k, d=None: d)})()
t2 = __import__("importlib").reload(t)   # real settings again for the card (read only)
def glass(title):
    w = QtWidgets.QFrame(); lay = QtWidgets.QVBoxLayout(w); return w, lay
card = agent_models.build_agent_models_card(ui, glass, QtGui.QFont())
check("card builds with explanation + external box", hasattr(ui, "checkBox_tool_ext") and hasattr(ui, "pushButton_tool_ext_test"))

print("\nFEHLER: " + ", ".join(bad) if bad else "\nAlles in Ordnung.")
sys.exit(1 if bad else 0)
