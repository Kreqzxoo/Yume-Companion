"""Update from GitHub: version comparison (beta12 -> beta13), choice of the setup file in a release, safety checks of the download
(address, checksum, size, cancel) and the start of the setup. A local HTTP server plays GitHub; nothing is installed."""
import hashlib, http.server, os, sys, tempfile, threading
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, ".")
from pathlib import Path
from app.utils import update_checker as uc, update_installer as ui

ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)

# ------------------------------------------------------------------ versions: every release must be found by the program before it
check("beta13 is newer than installed beta12", uc.is_newer("v3.0.0-beta13", "3.0.0-beta12"))
check("beta12 is not newer than installed beta12", not uc.is_newer("v3.0.0-beta12", "3.0.0-beta12"))
check("beta12 is newer than the first 3.0.0 BETA", uc.is_newer("v3.0.0-beta12", "3.0.0 BETA"))
check("beta10 is not a downgrade target", not uc.is_newer("v3.0.0-beta10", "3.0.0-beta12"))
check("beta100 sorts above beta99", uc.is_newer("v3.0.0-beta100", "3.0.0-beta99"))
check("3.0.1 is newer than every 3.0.0 beta", uc.is_newer("v3.0.1", "3.0.0-beta12"))

# ------------------------------------------------------------------ choice of the setup file
H = "ab" * 32
release = {"tag_name": "v3.0.0-beta13", "assets": [
    {"name": "Yume-Companion.apk", "browser_download_url": "https://github.com/o/r/releases/download/v3.0.0-beta13/Yume-Companion.apk", "size": 5},
    {"name": "Yume-Companion-Setup-3.0.0-beta13.exe", "browser_download_url": "https://github.com/o/r/releases/download/v3.0.0-beta13/Yume-Companion-Setup-3.0.0-beta13.exe",
     "size": 1000, "digest": "sha256:" + H, "state": "uploaded"},
    {"name": "Yume-Companion-Setup-3.0.0-beta13.exe.sha256", "browser_download_url": "https://github.com/o/r/releases/download/v3.0.0-beta13/Yume-Companion-Setup-3.0.0-beta13.exe.sha256", "size": 100},
    {"name": "Yume-LLM-Server-Setup-1.0.0.exe", "browser_download_url": "https://github.com/o/r/releases/download/v3.0.0-beta13/Yume-LLM-Server-Setup-1.0.0.exe", "size": 9}]}
s = uc.pick_setup(release)
check("setup found, APK and LLM server setup ignored", s["setup_name"] == "Yume-Companion-Setup-3.0.0-beta13.exe" and s["setup_size"] == 1000)
check("digest and checksum file found", s["sha256"] == H and s["sha256_url"].endswith(".exe.sha256"))
check("release without setup gives nothing", uc.pick_setup({"assets": [release["assets"][0]]})["setup_url"] == "")
check("bad digest is ignored", uc.pick_setup({"assets": [dict(release["assets"][1], digest="sha256:xyz")]})["sha256"] == "")

# ------------------------------------------------------------------ address checks (real rules, not the test switch)
good = {"repo": "o/r", "setup_name": s["setup_name"], "setup_url": release["assets"][1]["browser_download_url"], "setup_size": 1000, "sha256": H, "sha256_url": ""}
def refuses(key, **changes):
    try:
        ui.validate(dict(good, **changes)); return False
    except ui.UpdateError as e:
        return e.key == key
check("valid release address accepted", ui.validate(good)["name"] == s["setup_name"])
check("other host refused", refuses("bad_url", setup_url="https://evil.example/o/r/releases/download/v3/" + s["setup_name"]))
check("plain http refused", refuses("bad_url", setup_url=good["setup_url"].replace("https", "http")))
check("other repository refused", refuses("bad_url", repo="x/y"))
check("file outside the release path refused", refuses("bad_url", setup_url="https://github.com/o/r/raw/main/" + s["setup_name"]))
check("odd file name refused", refuses("bad_url", setup_name="evil.exe", setup_url="https://github.com/o/r/releases/download/v3/evil.exe"))
check("no checksum -> nothing is installed", refuses("no_checksum", sha256="", sha256_url=""))
check("no setup in the release", refuses("no_setup", setup_url="", setup_name=""))

# ------------------------------------------------------------------ download from a local "GitHub"
ui.ALLOW_INSECURE_FOR_TESTS = True
tmp = Path(tempfile.mkdtemp()); os.environ["LOCALAPPDATA"] = str(tmp)
payload = b"MZ" + os.urandom(3 * 1024 * 1024)
name = "Yume-Companion-Setup-3.0.0-beta13.exe"
files = {"/f/" + name: payload, "/f/" + name + ".sha256": (hashlib.sha256(payload).hexdigest() + "  " + name + "\n").encode(),
         "/f/bad.sha256": (("0" * 64) + "  x\n").encode(), "/f/text.exe": b"hello"}
class Srv(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        body = files.get(self.path)
        if body is None:
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
        try: self.wfile.write(body)
        except OSError: pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Srv); threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}/f/"
res = {"repo": "o/r", "setup_name": name, "setup_url": base + name, "setup_size": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "sha256_url": ""}
seen = []
path = ui.download_and_verify(res, lambda d, t: seen.append((d, t)))
check("download verified and stored", path.is_file() and path.read_bytes() == payload and path.parent == ui.updates_dir())
check("progress reported up to the full size", seen and seen[-1] == (len(payload), len(payload)))
check("no .part file left", not list(ui.updates_dir().glob("*.part")))
res2 = dict(res, sha256="", sha256_url=base + name + ".sha256")
check("checksum file alone is enough", ui.download_and_verify(res2).is_file())
def fails(key, r, **kw):
    try:
        ui.download_and_verify(r, **kw); return False
    except ui.UpdateError as e:
        return e.key == key and not list(ui.updates_dir().glob("*"))
check("wrong checksum -> file deleted, error", fails("hash_mismatch", dict(res, sha256="1" * 64)))
check("digest and checksum file disagree", fails("hash_conflict", dict(res, sha256="2" * 64, sha256_url=base + name + ".sha256")))
check("wrong announced size -> error", fails("size_mismatch", dict(res, setup_size=len(payload) + 5)))
fake = b"X" * len(payload)
files["/f/" + name] = fake
check("changed file -> checksum error", fails("hash_mismatch", res))
check("not a Windows program is refused even with a matching checksum", fails("not_exe", dict(res, sha256=hashlib.sha256(fake).hexdigest())))
files["/f/" + name] = payload
check("cancel during download -> nothing left", fails("cancelled", res, cancelled=lambda: True))
check("missing file -> network error", fails("network", dict(res, setup_url=base + "gone-" + name, setup_name=name)))

# ------------------------------------------------------------------ start of the setup
started = []
real = ui.subprocess.Popen
ui.subprocess.Popen = lambda cmd, **kw: started.append((cmd, kw))
good_path = ui.download_and_verify(res)
ui.launch_setup(good_path)
check("setup started as a plain program (no shell)", started and started[0][0] == [str(good_path)] and not started[0][1].get("shell"))
try:
    ui.launch_setup(tmp / "other" / name); bad = False
except ui.UpdateError:
    bad = True
check("a file outside the update folder is never started", bad and len(started) == 1)
ui.subprocess.Popen = real
srv.shutdown()
print("ALL OK" if ok else "FAILED"); sys.exit(0 if ok else 1)
