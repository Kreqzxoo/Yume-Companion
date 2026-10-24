import sys, os, re, json
os.environ["QT_QPA_PLATFORM"]="offscreen"
sys.path.insert(0,'.')
from types import SimpleNamespace
from app.utils.dashboard_server import DashboardServer, DASHBOARD_HTML
from fastapi.testclient import TestClient
api = SimpleNamespace(get_token=lambda k: {"REMOTE_LLM_BASE_URL":"http://192.168.1.50:8080/v1","REMOTE_LLM_API_TOKEN":""}.get(k,""))
cfg = SimpleNamespace(get_main_setting=lambda k: 8192 if k=="context_size" else None)
sig = SimpleNamespace(configuration_api=api, configuration_settings=cfg, tool_registry=SimpleNamespace(tool_names=lambda: []))
s = DashboardServer(sig, "tok")
c = TestClient(s.app, base_url="http://127.0.0.1", headers={"X-Dashboard-Token":"tok"})
r = c.get("/api/extra"); print(r.status_code); print(json.dumps(r.json(), indent=1)[:1200])
open(os.environ["TEMP"]+"/dash.html","w",encoding="utf-8").write(DASHBOARD_HTML)
js = re.search(r"<script>(.*)</script>", DASHBOARD_HTML, re.S).group(1)
open(os.environ["TEMP"]+"/dash.js","w",encoding="utf-8").write(js)
