import sys, os, json, asyncio
sys.path.insert(0,'.')
os.environ["QT_QPA_PLATFORM"]="offscreen"
from app.utils import spotify_pc as sp
print("connected:", sp.connected(), "client:", sp.client_id()[:6])
print("devices:", sp.devices())
print("search:", sp.search("Last Christmas Wham", "track", 3))
print("now:", sp.now_playing(0))
print("playlists:", [p["name"] for p in sp.my_playlists(5)])
