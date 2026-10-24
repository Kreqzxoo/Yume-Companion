"""Spotify on the PC (Web API, PKCE: no client secret is needed or stored).

The user enters the Client ID of their own Spotify app once and logs in once in the browser. The same login is handed to the phone
(Android Connector), so the PC dashboard, the PC and the phone all control and show the same player.
Playback control needs Spotify Premium.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

logger = logging.getLogger("Spotify")

APP_ROOT = Path(__file__).resolve().parents[2]
STORE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion" / "spotify.bin"      # outside the project: never in backups or releases
OLD_STORE = APP_ROOT / "app" / "data" / ".soul" / "spotify.json"                                        # earlier versions (plain text)
CALLBACK_PORT = 8898
REDIRECT_URI = f"http://127.0.0.1:{CALLBACK_PORT}/callback"
SCOPES = ("user-read-playback-state user-modify-playback-state user-read-currently-playing "
          "playlist-read-private user-library-read")

_lock = threading.RLock()
_login: dict = {}              # verifier / state of a login that is running
_now_cache: dict = {"t": 0.0, "data": None}
status_text = ""


# ------------------------------------------------------------------ storage
def _dpapi(data: bytes, protect: bool) -> bytes | None:
    """Windows data protection (only this Windows user can read the file). Returns None when it is not possible."""
    try:
        import ctypes
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        buf = ctypes.create_string_buffer(data, len(data))
        src = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        out = Blob()
        fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
        ok = fn(ctypes.byref(src), None, None, None, None, 0, ctypes.byref(out)) if protect else fn(ctypes.byref(src), None, None, None, None, 0, ctypes.byref(out))
        if not ok:
            return None
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out.pbData)
    except Exception:
        return None


def _load() -> dict:
    try:
        raw = STORE.read_bytes()
        plain = _dpapi(raw, protect=False)
        if plain is not None:
            return json.loads(plain.decode("utf-8"))
        return json.loads(raw.decode("utf-8"))                      # no data protection available: plain fallback
    except (OSError, ValueError):
        pass
    try:                                                            # migrate the login of an older version, then remove the plain file
        data = json.loads(OLD_STORE.read_text(encoding="utf-8"))
        if data:
            _save(data)
            OLD_STORE.unlink()
        return data
    except (OSError, ValueError):
        return {}


def _save(data: dict):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data).encode("utf-8")
    blob = _dpapi(payload, protect=True) or payload
    tmp = STORE.with_suffix(".tmp")
    tmp.write_bytes(blob)
    tmp.replace(STORE)


def client_id() -> str:
    return str(_load().get("client_id", "")).strip()


def set_client_id(value: str):
    with _lock:
        data = _load()
        value = (value or "").strip()
        if value != data.get("client_id"):
            data = {"client_id": value}                 # another app: the old login is not valid for it
        _save(data)


def connected() -> bool:
    return bool(_load().get("refresh_token"))


def credentials() -> dict:
    """What the phone needs to use the same account (Client ID + refresh token; PKCE refresh tokens need no secret)."""
    d = _load()
    return {"client_id": d.get("client_id", ""), "refresh_token": d.get("refresh_token", ""), "connected": bool(d.get("refresh_token"))}


def adopt(client: str, refresh_token: str) -> bool:
    """The phone was logged in first: take over its login (only when the PC has none yet)."""
    with _lock:
        d = _load()
        if not client or not refresh_token:
            return False
        if d.get("refresh_token") and d.get("client_id") == client.strip():
            return False                                    # the PC has the same login already
        if d.get("refresh_token"):
            return False                                    # another app: the PC's own login stays
        _save({"client_id": client.strip(), "refresh_token": refresh_token.strip()})
    return True


def logout():
    with _lock:
        d = _load()
        _save({"client_id": d.get("client_id", "")})
    _now_cache.update(t=0.0, data=None)


# ------------------------------------------------------------------ login (PKCE, loopback redirect)
def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _post_token(form: dict) -> dict | None:
    req = urllib.request.Request("https://accounts.spotify.com/api/token", data=urllib.parse.urlencode(form).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        logger.warning("Spotify token request refused: %s %s", exc.code, exc.read()[:200])
    except Exception as exc:
        logger.warning("Spotify token request failed: %s", exc)
    return None


def start_login() -> str:
    """Returns the URL to open in the browser; a tiny local server waits for the answer (2 minutes)."""
    global status_text
    cid = client_id()
    if not cid:
        raise ValueError("Bitte zuerst die Client-ID eintragen.")
    verifier = _b64(secrets.token_bytes(64))
    state = secrets.token_urlsafe(16)
    _login.clear()
    _login.update(verifier=verifier, state=state)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            global status_text
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            ok = False
            if q.get("state", [""])[0] == _login.get("state") and q.get("code"):
                res = _post_token({"grant_type": "authorization_code", "code": q["code"][0], "redirect_uri": REDIRECT_URI,
                                   "client_id": cid, "code_verifier": _login.get("verifier", "")})
                if res and res.get("refresh_token"):
                    with _lock:
                        _save({"client_id": cid, "refresh_token": res["refresh_token"], "access": res.get("access_token", ""),
                               "expires": time.time() + float(res.get("expires_in", 3600)) - 60})
                    ok = True
            status_text = "Mit Spotify verbunden." if ok else (
                "Spotify hat die Anmeldung nicht akzeptiert. Stimmt die Client-ID und ist die Redirect-URI in der Spotify-App eingetragen?")
            body = ("<html><body style='font-family:sans-serif;background:#1a1226;color:#fff;text-align:center;padding-top:80px'>"
                    f"<h2>{'Verbunden - du kannst dieses Fenster schließen.' if ok else 'Anmeldung fehlgeschlagen.'}</h2></body></html>").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    try:
        server = HTTPServer(("127.0.0.1", CALLBACK_PORT), Handler)
    except OSError as exc:
        raise ValueError(f"Port {CALLBACK_PORT} ist belegt ({exc}).")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    timer = threading.Timer(120, lambda: threading.Thread(target=server.shutdown, daemon=True).start())
    timer.daemon = True                                 # must not keep the program alive when it is closed
    timer.start()
    status_text = "Warte auf die Anmeldung im Browser …"
    return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": cid, "response_type": "code", "redirect_uri": REDIRECT_URI, "scope": SCOPES,
        "state": state, "code_challenge_method": "S256", "code_challenge": _b64(hashlib.sha256(verifier.encode()).digest())})


# ------------------------------------------------------------------ API
def _access() -> str | None:
    with _lock:
        d = _load()
        if d.get("access") and float(d.get("expires", 0)) > time.time():
            return d["access"]
        if not d.get("refresh_token") or not d.get("client_id"):
            return None
        res = _post_token({"grant_type": "refresh_token", "refresh_token": d["refresh_token"], "client_id": d["client_id"]})
        if not res or not res.get("access_token"):
            return None
        d["access"] = res["access_token"]
        d["expires"] = time.time() + float(res.get("expires_in", 3600)) - 60
        if res.get("refresh_token"):
            d["refresh_token"] = res["refresh_token"]
        _save(d)
        return d["access"]


def api(method: str, path: str, params: dict | None = None, body: dict | None = None):
    """Returns (status, json|None). 204 = ok without content."""
    token = _access()
    if not token:
        return 401, None
    url = "https://api.spotify.com/v1" + path + (("?" + urllib.parse.urlencode(params)) if params else "")
    data = json.dumps(body).encode() if body is not None else (b"" if method in ("PUT", "POST") else None)
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return r.status, (json.loads(raw.decode()) if raw else None)
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode())
        except Exception:
            return exc.code, None
    except Exception as exc:
        logger.debug("Spotify API failed: %s", exc)
        return 0, None


def now_playing(max_age: float = 3.0) -> dict:
    """{connected, playing, title, artist, album, device, volume, progress_ms, duration_ms, image}"""
    if not connected():
        return {"connected": False}
    if _now_cache["data"] is not None and time.time() - _now_cache["t"] < max_age:
        return _now_cache["data"]
    status, j = api("GET", "/me/player", {"additional_types": "track"})
    out: dict = {"connected": True, "playing": False}
    if status == 200 and j and j.get("item"):
        item = j["item"]
        images = (item.get("album") or {}).get("images") or []
        out.update(playing=bool(j.get("is_playing")), title=item.get("name", ""),
                   artist=", ".join(a.get("name", "") for a in item.get("artists", [])), album=(item.get("album") or {}).get("name", ""),
                   device=(j.get("device") or {}).get("name", ""), volume=(j.get("device") or {}).get("volume_percent"),
                   progress_ms=j.get("progress_ms") or 0, duration_ms=item.get("duration_ms") or 0,
                   image=(images[-1]["url"] if images else ""))
    elif status == 204:
        out["idle"] = True                              # logged in, but no player is active
    elif status == 401:
        out["error"] = "Anmeldung abgelaufen - bitte neu anmelden."
    elif status == 403:
        out["error"] = "Spotify Premium wird für die Steuerung benötigt."
    _now_cache.update(t=time.time(), data=out)
    return out


def control(action: str, value=None) -> tuple[bool, str]:
    action = (action or "").lower()
    calls = {
        "pause": ("PUT", "/me/player/pause", None, None),
        "resume": ("PUT", "/me/player/play", None, None),
        "next": ("POST", "/me/player/next", None, None),
        "previous": ("POST", "/me/player/previous", None, None),
    }
    if action == "volume":
        call = ("PUT", "/me/player/volume", {"volume_percent": max(0, min(100, int(value or 0)))}, None)
    elif action in calls:
        call = calls[action]
    else:
        return False, "Unbekannte Aktion"
    status, j = api(call[0], call[1], call[2], call[3])
    if status == 404 and action != "pause":
        dev_id, _ = ensure_device()                     # nothing active: wake up / start a device and try again
        if dev_id:
            status, j = api(call[0], call[1], {**(call[2] or {}), "device_id": dev_id}, call[3])
    _now_cache["t"] = 0.0
    if status in (200, 202, 204):
        return True, "ok"
    if status == 404:
        return False, "Kein aktives Wiedergabegerät - starte Spotify einmal am Handy oder PC."
    if status == 403:
        return False, "Spotify Premium wird für die Steuerung benötigt."
    return False, f"Spotify-Fehler {status}"


def play_query(query: str, kind: str = "track") -> tuple[bool, str]:
    kind = kind if kind in ("track", "album", "playlist", "artist") else "track"
    status, j = api("GET", "/search", {"q": query, "type": kind, "limit": 1})
    if status != 200 or not j:
        return False, f"Suche fehlgeschlagen ({status})"
    items = (j.get(kind + "s") or {}).get("items") or []
    if not items:
        return False, "Nichts gefunden"
    item = items[0]
    body = {"uris": [item["uri"]]} if kind == "track" else {"context_uri": item["uri"]}
    st, _ = api("PUT", "/me/player/play", None, body)
    _now_cache["t"] = 0.0
    if st in (200, 202, 204):
        return True, item.get("name", "")
    return (False, "Kein aktives Wiedergabegerät - starte Spotify einmal am Handy oder PC.") if st == 404 else (False, f"Spotify-Fehler {st}")


# ------------------------------------------------------------------ everything the AI needs (devices, search, queue, playlists ...)
NO_DEVICE = "Kein Spotify-Gerät gefunden. Öffne Spotify einmal am Handy oder PC."


def devices() -> list[dict]:
    status, j = api("GET", "/me/player/devices")
    return (j or {}).get("devices", []) if status == 200 else []


def _open_pc_spotify():
    """Starts the Spotify app on this PC (if it is installed) so that it appears as a playback device."""
    try:
        import os
        os.startfile("spotify:")             # type: ignore[attr-defined]
        return True
    except Exception:
        return False


def ensure_device(prefer: str = "") -> tuple[str | None, str]:
    """(device_id, message). Uses the active device; otherwise wakes one up: the named one, the phone, the PC; starts Spotify on the PC if needed."""
    for attempt in range(3):
        devs = devices()
        if devs:
            active = next((d for d in devs if d.get("is_active")), None)
            if active and not prefer:
                return active["id"], active.get("name", "")
            wanted = None
            if prefer:
                wanted = next((d for d in devs if prefer.lower() in str(d.get("name", "")).lower() or prefer.lower() == str(d.get("type", "")).lower()), None)
            wanted = wanted or active or next((d for d in devs if str(d.get("type", "")).lower() == "smartphone"), None) or devs[0]
            if not wanted.get("is_active"):
                api("PUT", "/me/player", None, {"device_ids": [wanted["id"]], "play": False})
                time.sleep(0.8)
            return wanted["id"], wanted.get("name", "")
        if attempt == 0:
            _open_pc_spotify()
        time.sleep(4)
    return None, NO_DEVICE


def search(query: str, kind: str = "track", limit: int = 5) -> list[dict]:
    kind = kind if kind in ("track", "album", "playlist", "artist") else "track"
    status, j = api("GET", "/search", {"q": query, "type": kind, "limit": max(1, min(limit, 10))})
    if status != 200 or not j:
        return []
    out = []
    for it in (j.get(kind + "s") or {}).get("items") or []:
        if not it:
            continue
        artist = ", ".join(a.get("name", "") for a in it.get("artists", [])) if it.get("artists") else (it.get("owner") or {}).get("display_name", "")
        out.append({"name": it.get("name", ""), "artist": artist, "uri": it.get("uri", ""), "kind": kind})
    return out


def play(query: str, kind: str = "track", device: str = "") -> tuple[bool, str]:
    """Search and start the best match on a device (woken up if necessary)."""
    found = search(query, kind, 3)
    if not found:
        return False, f"Nichts gefunden für „{query}“."
    dev_id, dev_name = ensure_device(device)
    if not dev_id:
        return False, dev_name
    item = found[0]
    body = {"uris": [item["uri"]]} if item["kind"] == "track" else {"context_uri": item["uri"]}
    st, j = api("PUT", "/me/player/play", {"device_id": dev_id}, body)
    _now_cache["t"] = 0.0
    if st in (200, 202, 204):
        who = f" von {item['artist']}" if item["artist"] else ""
        return True, f"Spiele {item['name']}{who} auf {dev_name}."
    if st == 403:
        return False, "Spotify Premium wird für die Steuerung benötigt."
    return False, f"Spotify-Fehler {st}"


def queue_add(query: str) -> tuple[bool, str]:
    found = search(query, "track", 1)
    if not found:
        return False, f"Nichts gefunden für „{query}“."
    dev_id, _ = ensure_device()
    st, _ = api("POST", "/me/player/queue", {"uri": found[0]["uri"], **({"device_id": dev_id} if dev_id else {})})
    return (st in (200, 202, 204)), (f"{found[0]['name']} zur Warteschlange hinzugefügt." if st in (200, 202, 204) else f"Spotify-Fehler {st}")


def set_shuffle(on: bool) -> tuple[bool, str]:
    st, _ = api("PUT", "/me/player/shuffle", {"state": "true" if on else "false"})
    return st in (200, 202, 204), ("Zufallswiedergabe an." if on else "Zufallswiedergabe aus.") if st in (200, 202, 204) else f"Spotify-Fehler {st}"


def set_repeat(mode: str) -> tuple[bool, str]:
    mode = mode if mode in ("off", "track", "context") else "off"
    st, _ = api("PUT", "/me/player/repeat", {"state": mode})
    return st in (200, 202, 204), f"Wiederholen: {mode}." if st in (200, 202, 204) else f"Spotify-Fehler {st}"


def my_playlists(limit: int = 20) -> list[dict]:
    st, j = api("GET", "/me/playlists", {"limit": max(1, min(limit, 50))})
    return [{"name": p.get("name", ""), "uri": p.get("uri", "")} for p in (j or {}).get("items", []) if p] if st == 200 else []


def play_liked(device: str = "") -> tuple[bool, str]:
    st, j = api("GET", "/me/tracks", {"limit": 50})
    uris = [it["track"]["uri"] for it in (j or {}).get("items", []) if it.get("track")] if st == 200 else []
    if not uris:
        return False, "Keine gespeicherten Titel gefunden (oder die Berechtigung fehlt - bitte neu anmelden)."
    dev_id, dev_name = ensure_device(device)
    if not dev_id:
        return False, dev_name
    st, _ = api("PUT", "/me/player/play", {"device_id": dev_id}, {"uris": uris})
    _now_cache["t"] = 0.0
    return st in (200, 202, 204), (f"Spiele deine gespeicherten Titel auf {dev_name}." if st in (200, 202, 204) else f"Spotify-Fehler {st}")


def play_my_playlist(name: str, device: str = "") -> tuple[bool, str]:
    wanted = name.lower().strip()
    pl = next((p for p in my_playlists(50) if wanted in p["name"].lower()), None)
    if not pl:
        return False, f"Keine eigene Playlist namens „{name}“ gefunden."
    dev_id, dev_name = ensure_device(device)
    if not dev_id:
        return False, dev_name
    st, _ = api("PUT", "/me/player/play", {"device_id": dev_id}, {"context_uri": pl["uri"]})
    _now_cache["t"] = 0.0
    return st in (200, 202, 204), (f"Spiele die Playlist {pl['name']} auf {dev_name}." if st in (200, 202, 204) else f"Spotify-Fehler {st}")


def transfer(device: str) -> tuple[bool, str]:
    dev_id, dev_name = ensure_device(device or "")
    if not dev_id:
        return False, dev_name
    st, _ = api("PUT", "/me/player", None, {"device_ids": [dev_id], "play": True})
    return st in (200, 202, 204), (f"Wiedergabe auf {dev_name} verschoben." if st in (200, 202, 204) else f"Spotify-Fehler {st}")
