"""Finds the packages of the working folder's Python environment that installer.bat does NOT install.

Those packages came with the original program archive (for example the modified rvc_python and the prebuilt
fairseq wheel). A clean copy has to keep them, everything else is re-installed by installer.bat.

Run with the environment's own python:   python env_delta.py <installer.bat> <out.json>
"""
import json
import re
import shlex
import sys
from importlib import metadata as md
from pathlib import Path

installer = Path(sys.argv[1])
out_file = Path(sys.argv[2])


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


# ---------------------------------------------------------------- what installer.bat requests
requested: dict[str, set] = {}
for raw in installer.read_text(encoding="utf-8", errors="replace").splitlines():
    line = raw.strip()
    if not re.search(r"(:pipi\b|pip install)", line, re.I) or line.lower().startswith(("rem ", "echo", "::")):
        continue
    line = re.sub(r"^.*?(:pipi|pip install)\b", "", line, flags=re.I)
    try:
        tokens = shlex.split(line, posix=False)
    except ValueError:
        tokens = line.split()
    skip_next = False
    for tok in tokens:
        tok = tok.strip('"\'')
        if skip_next:
            skip_next = False
            continue
        if tok.startswith("-"):
            skip_next = tok in ("--index-url", "--extra-index-url", "-r", "-c", "--find-links", "-f")
            continue
        if not tok or "://" in tok or "%" in tok or "!" in tok or tok.endswith(".whl") or tok in ("&&", "||", "^", ")"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)(\[([^\]]+)\])?", tok)
        if not m or not re.match(r"^[A-Za-z]", m.group(1)):
            continue
        extras = set(x.strip() for x in (m.group(3) or "").split(",") if x.strip())
        requested.setdefault(norm(m.group(1)), set()).update(extras)
requested.setdefault("flash-attn", set())          # installed from a wheel by installer.bat (optional step)
requested.setdefault("pywebrtc-audio", set())

# ---------------------------------------------------------------- dependency closure inside this environment
try:
    from packaging.requirements import Requirement
except Exception:                                   # pip vendors packaging
    from pip._vendor.packaging.requirements import Requirement

dists = {}
for d in md.distributions():
    name = d.metadata["Name"]
    if name:
        dists[norm(name)] = d

closure: set = set()
queue = [(n, ex) for n, ex in requested.items()]
while queue:
    name, extras = queue.pop()
    if name in closure and not extras:
        continue
    closure.add(name)
    d = dists.get(name)
    if d is None:
        continue
    for r in d.requires or []:
        try:
            req = Requirement(r)
        except Exception:
            continue
        ok = False
        if req.marker is None:
            ok = True
        else:
            for e in (extras | {""}):
                try:
                    if req.marker.evaluate({"extra": e}):
                        ok = True
                        break
                except Exception:
                    ok = True
        if ok:
            n = norm(req.name)
            if n not in closure:
                queue.append((n, set(req.extras)))

# ---------------------------------------------------------------- the rest = shipped with the original archive
ALWAYS_SKIP = {"pip", "setuptools", "wheel", "pkg-resources", "packaging", "distlib"}
origin_extras = {n for n in dists if n not in closure and n not in ALWAYS_SKIP}

# the shipped packages need their own dependencies at run time - take every dependency that installer.bat does not
# request explicitly with them (the dependency graph of a *different* package set cannot be trusted to cover them)
needed: set = set()
# default OFF: a real installer.bat run (verified against a fresh install) already pulls the dependencies of its packages;
# pass --with-deps to ship them as well
queue = list(origin_extras) if "--with-deps" in sys.argv else []
while queue:
    name = queue.pop()
    d = dists.get(name)
    if d is None:
        continue
    for r in d.requires or []:
        try:
            req = Requirement(r)
        except Exception:
            continue
        try:
            if req.marker is not None and not req.marker.evaluate({"extra": ""}):
                continue
        except Exception:
            pass
        n = norm(req.name)
        if n in needed or n in origin_extras or n in requested or n in ALWAYS_SKIP or n not in dists:
            continue
        if n.startswith(("nvidia-", "torch", "triton")):
            continue
        needed.add(n)
        queue.append(n)

extras_found = []
keep_entries: set = set()
for name, d in sorted(dists.items()):
    if name not in origin_extras and name not in needed:
        continue
    entries, size = set(), 0
    for f in d.files or []:
        parts = Path(str(f)).parts
        if not parts or parts[0] in ("..", "__pycache__") or parts[0].endswith(".exe"):
            continue
        entries.add(parts[0])
        try:
            size += (Path(d.locate_file(f))).stat().st_size
        except OSError:
            pass
    entries = {e for e in entries if e != "__pycache__"}
    extras_found.append({"name": name, "version": d.version, "mb": round(size / 1048576, 1), "entries": sorted(entries),
                         "why": "shipped with the original archive" if name in origin_extras else "dependency of a shipped package"})
    keep_entries |= entries

out_file.write_text(json.dumps({"requested": sorted(requested), "extras": extras_found, "keep_entries": sorted(keep_entries)}, indent=2), encoding="utf-8")
print(f"requested by installer.bat: {len(requested)} | in env: {len(dists)} | closure: {len(closure)} | extras: {len(extras_found)} | "
      f"{sum(e['mb'] for e in extras_found):.0f} MB")
