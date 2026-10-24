import sys, os, json, asyncio
sys.path.insert(0,'.')
os.environ["QT_QPA_PLATFORM"]="offscreen"
import requests
from app.utils.ai_clients import tools as T
sp = T.SpotifyTool()
schemas=[sp.get_schema(), T.PhoneControlTool().get_schema()]
sysmsg = "Du bist Yume. Antworte kurz auf Deutsch.\n[TOOL ROUTER]\nAvailable tools: spotify, phone. When the user asks for something a tool can do (music etc.) you MUST call the tool in this turn."
for q in ["spile mir bitte last chrismas auf spotify","spiel was von den Ärzten","stoppe die musik","was läuft gerade?","mach leiser auf 30","spiel meine Playlist Car","spiele das auf meinem handy"]:
    r = requests.post("http://192.168.1.50:8080/v1/chat/completions", json={"messages":[{"role":"system","content":sysmsg},{"role":"user","content":q}],"tools":schemas,"temperature":0.1,"max_tokens":300}, timeout=120).json()
    m = r["choices"][0]["message"]
    print(q, "=>", [(c["function"]["name"], c["function"]["arguments"]) for c in (m.get("tool_calls") or [])] or m.get("content","")[:100])
for a in ({"action":"devices"},{"action":"search","query":"Last Christmas","kind":"track"},{"action":"now"}):
    print(a["action"], "->", asyncio.run(sp.execute(a, {}))["result"][:200])
