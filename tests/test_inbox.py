"""Inbox: upload endpoint (raw file + text), tool 'list' / 'read' for text, PDF-less checks; transcription is faked. Temporary folders."""
import sys, os, asyncio, tempfile, types
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, '.')
from pathlib import Path
from types import SimpleNamespace
from app.utils import inbox
tmp = Path(tempfile.mkdtemp())
inbox.DIR = tmp / "Eingang"; inbox.INDEX = tmp / "inbox.json"
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
from app.utils.web_server import WebBridge
cfg = SimpleNamespace(get_main_setting=lambda k: None)
signals = SimpleNamespace(configuration_settings=cfg, configuration_characters=SimpleNamespace(load_configuration=lambda: {"character_list": {}}), configuration_api=SimpleNamespace(get_token=lambda k: ""),
                          current_active_character="", web_server_running=True)
bridge = WebBridge(signals, auth_token="tok")
from fastapi.testclient import TestClient
c = TestClient(bridge.app, base_url="http://127.0.0.1", headers={"X-Yume-Token": "tok"})
r = c.post("/api/inbox?name=Sprachnachricht.opus&mime=audio/ogg", content=b"OggS" + b"\0" * 2000)
check("upload accepted", r.status_code == 200 and r.json()["kind"] == "audio")
r2 = c.post("/api/inbox/text", json={"text": "Hallo Yume, bitte merk dir: Rechnung bis Freitag bezahlen.", "title": "Notiz"})
check("text accepted", r2.status_code == 200 and r2.json()["kind"] == "text")
check("empty upload refused", c.post("/api/inbox?name=x.bin", content=b"").status_code == 400)
check("without token refused", TestClient(bridge.app, base_url="http://127.0.0.1").post("/api/inbox?name=a.txt", content=b"abc").status_code in (401, 403))
check("files saved in the inbox folder", len(list(inbox.DIR.iterdir())) == 2)
from app.utils.ai_clients import tools as T
bridge.transcribe_file = lambda path, language=None: "Treffen morgen um drei bei Anna, bring bitte den Kuchen mit."
ctx = {"system_ref": SimpleNamespace(web_bridge=bridge)}
lst = asyncio.run(T.InboxTool().execute({"action": "list"}, ctx))
check("list shows both", lst["result"].count("[id") == 2)
audio = [i for i in inbox.list_items() if i["kind"] == "audio"][0]
res = asyncio.run(T.InboxTool().execute({"action": "read", "id": audio["id"]}, ctx))
check("voice note transcribed", res["success"] and "Kuchen" in res["result"])
res = asyncio.run(T.InboxTool().execute({"action": "read", "id": "latest"}, ctx))
check("latest = the text note, read as text", res["success"] and "Rechnung" in res["result"])
check("unknown id", not asyncio.run(T.InboxTool().execute({"action": "read", "id": "zzzz"}, ctx))["success"])
print("ALL OK" if ok else "FAILED")
