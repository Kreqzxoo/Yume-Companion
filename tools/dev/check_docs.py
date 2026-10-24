"""
Prueft die Dokumentation: gibt es alle verlinkten Dateien, Bilder und Ueberschriften-Anker?
Aufruf (im Projektordner):  python tools/dev/check_docs.py
"""
import os
import re
import sys
import unicodedata

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MD = []
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "build", "__pycache__", "data", "archiv")]
    for f in files:
        if f.lower().endswith(".md"):
            MD.append(os.path.join(base, f))

LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEAD = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.M)


def slug(text):
    text = re.sub(r"`", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.strip().lower()
    out = []
    for ch in text:
        if ch.isalnum() or ch in "-_":
            out.append(ch)
        elif ch in " ":
            out.append("-")
        elif unicodedata.category(ch).startswith("L") or unicodedata.category(ch).startswith("N"):
            out.append(ch)
    return "".join(out)


anchors = {}


def anchors_of(path):
    if path not in anchors:
        txt = open(path, encoding="utf-8").read()
        txt = re.sub(r"```.*?```", "", txt, flags=re.S)
        seen = {}
        res = set()
        for _, h in HEAD.findall(txt):
            s = slug(h)
            n = seen.get(s, 0)
            seen[s] = n + 1
            res.add(s if n == 0 else f"{s}-{n}")
        anchors[path] = res
    return anchors[path]


bad = 0
for md in MD:
    txt = open(md, encoding="utf-8").read()
    txt_nocode = re.sub(r"```.*?```", "", txt, flags=re.S)
    for target in LINK.findall(txt_nocode):
        if re.match(r"^(https?:|mailto:|#$)", target):
            continue
        path, _, frag = target.partition("#")
        full = md if not path else os.path.normpath(os.path.join(os.path.dirname(md), path))
        if path and not os.path.exists(full):
            print(f"FEHLT   {os.path.relpath(md, ROOT)} -> {target}")
            bad += 1
            continue
        if frag and full.lower().endswith(".md") and frag not in anchors_of(full):
            print(f"ANKER?  {os.path.relpath(md, ROOT)} -> {target}")
            bad += 1
print("Dateien geprueft:", len(MD), "| Probleme:", bad)
sys.exit(1 if bad else 0)
