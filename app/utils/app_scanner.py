"""Finds installed Windows programs (Start-menu shortcuts, desktop shortcuts, registered App Paths) for the launcher tool."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_SKIP = re.compile(
    r"(?i)(uninstall|deinstall|entfern|remove|readme|read me|help|hilfe|license|lizenz|licence|website|webseite|support|"
    r"documentation|dokumentation|changelog|release notes|manual|handbuch|eula|privacy|datenschutz|updater?$|"
    r"web site|homepage|forum|feedback|faq|tutorial|survey|install(er)?$|^about |administrative tools|^windows tools)")


def _clean(name: str) -> str:
    name = re.sub(r"(?i)\s*-\s*(shortcut|verknüpfung)$", "", name).strip()
    return name.replace("|", " ").strip()


def _start_menu_dirs() -> list[Path]:
    dirs = []
    for env, sub in (("ProgramData", r"Microsoft\Windows\Start Menu\Programs"), ("APPDATA", r"Microsoft\Windows\Start Menu\Programs")):
        base = os.environ.get(env)
        if base:
            dirs.append(Path(base) / sub)
    return dirs


def _desktop_dirs() -> list[Path]:
    dirs = []
    for env, sub in (("PUBLIC", "Desktop"), ("USERPROFILE", "Desktop"), ("USERPROFILE", r"OneDrive\Desktop")):
        base = os.environ.get(env)
        if base:
            dirs.append(Path(base) / sub)
    return dirs


def _scan_shortcuts(dirs, recursive: bool) -> list[dict]:
    found = []
    for d in dirs:
        if not d.is_dir():
            continue
        iterator = d.rglob("*.lnk") if recursive else d.glob("*.lnk")
        try:
            for lnk in iterator:
                name = _clean(lnk.stem)
                if not name or _SKIP.search(name):
                    continue
                found.append({"name": name, "path": str(lnk), "source": "shortcut"})
        except OSError:
            continue
    return found


def _scan_app_paths() -> list[dict]:
    found = []
    if sys.platform != "win32":
        return found
    try:
        import winreg
    except ImportError:
        return found
    key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            root = winreg.OpenKey(hive, key_path)
        except OSError:
            continue
        with root:
            index = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, index)
                except OSError:
                    break
                index += 1
                if not sub.lower().endswith(".exe"):
                    continue
                try:
                    with winreg.OpenKey(root, sub) as k:
                        value, _ = winreg.QueryValueEx(k, "")
                except OSError:
                    continue
                path = os.path.expandvars(str(value).strip().strip('"'))
                if not path.lower().endswith(".exe") or not os.path.isfile(path):
                    continue
                name = _clean(Path(sub).stem).replace("_", " ")
                if name and not _SKIP.search(name):
                    found.append({"name": name[:1].upper() + name[1:], "path": path, "source": "registry"})
    return found


def _resolve_targets(lnk_paths: list[str]) -> dict[str, str]:
    """lnk -> target path via one hidden PowerShell call (WScript.Shell); empty dict if unavailable."""
    if not lnk_paths or sys.platform != "win32":
        return {}
    import json
    import subprocess
    import tempfile
    script = (
        "$ErrorActionPreference='SilentlyContinue';$sh=New-Object -ComObject WScript.Shell;"
        "$paths=Get-Content -LiteralPath $args[0] -Encoding UTF8;"
        "$out=@{};foreach($p in $paths){$out[$p]=$sh.CreateShortcut($p).TargetPath};"
        "$out|ConvertTo-Json -Compress"
    )
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
            fh.write("\n".join(lnk_paths))
            list_file = fh.name
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
             "& { " + script + " }", list_file],
            capture_output=True, text=True, timeout=40, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        os.unlink(list_file)
        data = json.loads(proc.stdout.strip() or "{}")
        return {k: (v or "") for k, v in data.items()}
    except Exception:
        return {}


def scan() -> list[dict]:
    """Returns [{'name', 'path', 'source'}] sorted by name, one entry per program name."""
    shortcuts = _scan_shortcuts(_start_menu_dirs(), True) + _scan_shortcuts(_desktop_dirs(), False)
    targets = _resolve_targets([e["path"] for e in shortcuts])
    entries = []
    known_exes = set()
    for e in shortcuts:
        if targets:
            target = targets.get(e["path"], "")
            low = target.lower()
            if not low.endswith(".exe") or "unins" in Path(low).stem or "uninstall" in low:
                continue            # documents, web links, folders, Store apps ...
            known_exes.add(os.path.normcase(target))
            e["target"] = target
        entries.append(e)
    stems = {Path(e["path"]).stem.casefold() for e in entries} | {e["name"].casefold() for e in entries}
    for e in _scan_app_paths():
        if e["name"].casefold() in stems or os.path.normcase(e["path"]) in known_exes:
            continue
        entries.append(e)
    unique: dict[str, dict] = {}
    for e in entries:
        unique.setdefault(e["name"].casefold(), e)
    return sorted(unique.values(), key=lambda e: e["name"].casefold())
