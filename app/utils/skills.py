"""Skills: small Python programs that Yume writes for herself when she lacks an ability ("hol mir den Bitcoin-Preis", "rechne Währungen um" ...).

Safety (honest description):
* A skill is only saved AFTER the user has read the code and agreed (confirmation dialog of the tool system).
* Before that the code is checked statically (no processes, no file writing / deleting, no dynamic code, no raw sockets, no registry / ctypes).
* It runs in its own short-lived Python process (time limit 25 s, output limit), never inside the program.
* A skill file that was changed after approval needs a new approval before it runs.
This is a safety net, not a perfect sandbox: it reduces mistakes, the real protection is that YOU approve the code. Skills may use the internet.

A skill file defines NAME, DESCRIPTION, PARAMETERS (JSON-schema "properties" dict) and  def run(args: dict) -> str.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion" / "skills"
APPROVALS = DIR / "approved.json"
TIMEOUT = 25
MAX_OUT = 8000
_lock = threading.RLock()

FORBIDDEN_IMPORTS = {"subprocess", "ctypes", "socket", "shutil", "multiprocessing", "winreg", "pickle", "marshal", "msvcrt", "pty", "signal", "importlib", "runpy", "builtins", "code", "pexpect", "paramiko"}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__", "breakpoint", "input", "globals", "locals", "vars", "setattr", "delattr"}
FORBIDDEN_OS = {"system", "popen", "remove", "unlink", "rmdir", "removedirs", "rename", "replace", "startfile", "kill", "killpg", "_exit", "chmod", "chown", "execv", "execl", "execvp",
                "spawnl", "spawnv", "fork", "walk_write", "makedirs", "mkdir", "truncate", "symlink", "link"}
FORBIDDEN_PATH_METHODS = {"write_text", "write_bytes", "unlink", "rmdir", "rename", "replace", "touch", "mkdir", "chmod", "symlink_to", "hardlink_to"}


def _name_ok(name: str) -> str:
    n = re.sub(r"[^a-z0-9_]", "", str(name or "").lower().replace(" ", "_").replace("-", "_"))[:40]
    return n if len(n) >= 3 and not n[0].isdigit() else ""


def validate(code: str) -> tuple[bool, list[str]]:
    """Static check. Returns (ok, problems in plain German)."""
    problems: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, [f"Syntaxfehler in Zeile {exc.lineno}: {exc.msg}"]
    defined = {"NAME": False, "DESCRIPTION": False, "run": False}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in defined:
                    defined[t.id] = True
        elif isinstance(node, ast.FunctionDef) and node.name == "run":
            defined["run"] = True
    for k, v in defined.items():
        if not v:
            problems.append(f"{k} fehlt (die Datei braucht NAME, DESCRIPTION, PARAMETERS und eine Funktion run(args))")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in FORBIDDEN_IMPORTS:
                    problems.append(f"Verbotener Import: {a.name}")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in FORBIDDEN_IMPORTS:
                problems.append(f"Verbotener Import: {node.module}")
            if (node.module or "") == "os" and any(a.name in FORBIDDEN_OS for a in node.names):
                problems.append("Verbotene os-Funktion importiert")
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                if f.id in FORBIDDEN_CALLS:
                    problems.append(f"Verbotener Aufruf: {f.id}()")
                if f.id == "open":
                    mode = ""
                    if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                        mode = str(node.args[1].value)
                    for kw in node.keywords:
                        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                            mode = str(kw.value.value)
                    if any(ch in mode for ch in "wax+"):
                        problems.append("Dateien schreiben ist nicht erlaubt")
            elif isinstance(f, ast.Attribute):
                if f.attr in FORBIDDEN_PATH_METHODS:
                    problems.append(f"Verbotene Datei-Aktion: .{f.attr}()")
                if isinstance(f.value, ast.Name) and f.value.id == "os" and f.attr in FORBIDDEN_OS:
                    problems.append(f"Verbotene os-Funktion: os.{f.attr}()")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr.endswith("__") and node.attr not in ("__name__", "__doc__", "__class__", "__dict__", "__len__"):
            problems.append(f"Verbotener Zugriff: {node.attr}")
    return (not problems), list(dict.fromkeys(problems))


def _meta(code: str) -> dict:
    """NAME / DESCRIPTION / PARAMETERS read without running the code."""
    out = {"name": "", "description": "", "parameters": {}}
    try:
        for node in ast.parse(code).body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                key = node.targets[0].id
                if key in ("NAME", "DESCRIPTION", "PARAMETERS"):
                    try:
                        out[{"NAME": "name", "DESCRIPTION": "description", "PARAMETERS": "parameters"}[key]] = ast.literal_eval(node.value)
                    except Exception:
                        pass
    except SyntaxError:
        pass
    return out


def _digest(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:20]


def _approvals() -> dict:
    try:
        return json.loads(APPROVALS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def create(name: str, code: str) -> tuple[bool, str]:
    """Saves the skill (the caller has to make sure the user approved the code)."""
    key = _name_ok(name)
    if not key:
        return False, "Der Name braucht mindestens 3 Buchstaben, Ziffern oder Unterstriche."
    ok, problems = validate(code)
    if not ok:
        return False, "Der Code ist nicht erlaubt: " + "; ".join(problems)
    meta = _meta(code)
    if not str(meta["description"]).strip():
        return False, "DESCRIPTION darf nicht leer sein."
    with _lock:
        DIR.mkdir(parents=True, exist_ok=True)
        (DIR / f"{key}.py").write_text(code, encoding="utf-8")
        ap = _approvals()
        ap[key] = _digest(code)
        APPROVALS.write_text(json.dumps(ap), encoding="utf-8")
    return True, f"Fähigkeit „{key}“ gespeichert."


def list_skills() -> list[dict]:
    out = []
    if DIR.is_dir():
        ap = _approvals()
        for f in sorted(DIR.glob("*.py")):
            try:
                code = f.read_text(encoding="utf-8")
            except OSError:
                continue
            meta = _meta(code)
            out.append({"name": f.stem, "description": str(meta["description"])[:200], "parameters": meta["parameters"] if isinstance(meta["parameters"], dict) else {},
                        "approved": ap.get(f.stem) == _digest(code), "path": str(f)})
    return out


def get(name: str) -> dict | None:
    key = _name_ok(name)
    return next((s for s in list_skills() if s["name"] == key), None)


def delete(name: str) -> bool:
    key = _name_ok(name)
    f = DIR / f"{key}.py"
    with _lock:
        if not key or not f.is_file():
            return False
        f.unlink()
        ap = _approvals()
        ap.pop(key, None)
        APPROVALS.write_text(json.dumps(ap), encoding="utf-8")
    return True


RUNNER = '''import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("yume_skill", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
args = json.loads(sys.argv[2])
out = mod.run(args)
sys.stdout.write("\\n@@YUME-RESULT@@" + json.dumps({"ok": True, "text": str(out)}, ensure_ascii=False))
'''


def run(name: str, args: dict) -> tuple[bool, str]:
    """Runs an approved skill in its own process. Returns (success, text)."""
    s = get(name)
    if s is None:
        return False, "Diese Fähigkeit gibt es nicht."
    if not s["approved"]:
        return False, "Diese Fähigkeit wurde nach der Freigabe verändert und braucht eine neue Freigabe."
    code = Path(s["path"]).read_text(encoding="utf-8")
    ok, problems = validate(code)
    if not ok:
        return False, "Der Code ist nicht erlaubt: " + "; ".join(problems)
    with tempfile.TemporaryDirectory(prefix="yume_skill_") as work:
        runner = Path(work) / "runner.py"
        runner.write_text(RUNNER, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k.upper() in ("SYSTEMROOT", "PATH", "TEMP", "TMP", "LANG", "PYTHONIOENCODING", "HOME", "USERPROFILE", "SSL_CERT_FILE")}
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            p = subprocess.run([sys.executable, "-I", str(runner), s["path"], json.dumps(args or {}, ensure_ascii=False)], cwd=work, env=env, capture_output=True, timeout=TIMEOUT,
                               creationflags=0x08000000 if os.name == "nt" else 0)
        except subprocess.TimeoutExpired:
            return False, f"Die Fähigkeit hat nach {TIMEOUT} Sekunden nicht geantwortet und wurde beendet."
        except Exception as exc:
            return False, f"Start fehlgeschlagen: {str(exc)[:100]}"
    stdout = p.stdout.decode("utf-8", "replace")
    if "@@YUME-RESULT@@" in stdout:
        try:
            data = json.loads(stdout.split("@@YUME-RESULT@@", 1)[1])
            return True, data["text"][:MAX_OUT]
        except ValueError:
            pass
    err = (p.stderr.decode("utf-8", "replace").strip().splitlines() or ["unbekannter Fehler"])[-1]
    return False, f"Fehler in der Fähigkeit: {err[:200]}"
