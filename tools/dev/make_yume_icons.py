"""Draws the Yume icon set (app/gui/icons/*.png) from the Windows icon font "Segoe Fluent Icons".

Run once on a Windows 11 PC (the PNG files are then part of the program, no font needed at runtime):

    app\\data\\envs\\sow\\python.exe tools\\dev\\make_yume_icons.py [--sheet out.png] [--dry]

* Brand logos (OpenAI, Gemini, Discord ...) and colour images are never touched.
* The original files are copied to  tools/dev/icons_original  the first time (so the script can be run again).
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

ROOT = Path(__file__).resolve().parents[2]
ICONS = ROOT / "app" / "gui" / "icons"
BACKUP = ROOT / "tools" / "dev" / "icons_original"
FONT = "Segoe Fluent Icons"

# file name (without .png) -> code point in Segoe Fluent Icons
GLYPHS = {
    "2D_face": 0xE899, "3D_cube": 0xE7B8, "add_folder": 0xE8F4, "ai": 0xE945, "arrowDown": 0xE70D, "attached": 0xE723, "author_notes": 0xE70B,
    "autoplay": 0xE768, "background_icon": 0xE91B, "bin": 0xE74D, "branch": 0xEA3C, "broom": 0xEA99, "chat": 0xE8BD, "checked": 0xE73E,
    "clapperboard": 0xE714, "close": 0xE711, "color-palette": 0xE790, "config": 0xE713, "continue": 0xE893, "create_character": 0xE8FA,
    "d20": 0xE7FC, "default_model": 0xE950, "delete": 0xE74D, "down_arrow": 0xE70D, "downloading": 0xE896, "edit": 0xE70F, "export": 0xE898,
    "expressions": 0xE899, "faq": 0xE897, "folder": 0xE8B7, "gateway": 0xE774, "gpu": 0xE950, "import": 0xE896, "import_image": 0xE91B,
    "information": 0xE946, "left_arrow": 0xE76B, "local_llm": 0xE7F4, "lorebook": 0xE82D, "main": 0xE80F, "map": 0xE809, "maximize": 0xE922,
    "maximize_minimize": 0xE923, "memory": 0xE950, "minimize": 0xE921, "modelshub": 0xE8F1, "models": 0xE8F1, "modules": 0xEA86,
    "more": 0xE712, "none": 0xE711, "options": 0xE713, "personas": 0xE716, "phone": 0xE717, "play": 0xE768, "plus": 0xE710,
    "popular": 0xE734, "recommendations": 0xE734, "regen": 0xE72C, "reload": 0xE72C, "rename": 0xE8AC, "replay": 0xE777,
    "right_arrow": 0xE76C, "rp_editors": 0xE70F, "save": 0xE74E, "search": 0xE721, "send": 0xE724, "soulMemory": 0xE95E,
    "soulMemory_book": 0xE82D, "soul_stage": 0xF1AD, "sowsystem": 0xE770, "stop": 0xE71A, "summary": 0xE8A5, "system": 0xE770,
    "system_prompt": 0xE756, "tools": 0xE90F, "tools_toggle": 0xE90F, "translator": 0xE775, "up_arrow": 0xE70E, "user": 0xE77B,
    "variable": 0xE943, "voice": 0xE720, "export_card": 0xE8A5,
}
KEEP = {"anthropic", "deepseek", "discord", "gemini", "github", "grok", "logotitle", "logotitle_black", "logotype", "mistralai", "openai", "openrouter",
        "person", "player2", "qwen", "star", "youtube", "zai"}
COLOR = (234, 226, 247)          # soft lavender white (the program tints / dims icons itself)


def draw(code: int, size: int, color=COLOR, stroke_fix=True) -> QtGui.QImage:
    img = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32)
    img.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
    f = QtGui.QFont(FONT)
    f.setPixelSize(int(size * 0.72))
    p.setFont(f)
    p.setPen(QtGui.QColor(*color))
    p.drawText(QtCore.QRectF(0, 0, size, size), QtCore.Qt.AlignmentFlag.AlignCenter, chr(code))
    p.end()
    return img


def main():
    app = QtWidgets.QApplication(sys.argv)
    if FONT not in QtGui.QFontDatabase.families():
        print(f'Die Schrift "{FONT}" fehlt (Windows 11 nötig). Nichts geändert.')
        return 1
    fm = QtGui.QFontMetrics(QtGui.QFont(FONT, 20))
    missing = [n for n, c in GLYPHS.items() if not fm.inFontUcs4(c)]
    if missing:
        print("Glyph fehlt in der Schrift:", missing)
    dry = "--dry" in sys.argv
    sheet = None
    if "--sheet" in sys.argv:
        sheet = Path(sys.argv[sys.argv.index("--sheet") + 1])
    if not dry:
        BACKUP.mkdir(exist_ok=True)
    done, tiles = 0, []
    for name, code in sorted(GLYPHS.items()):
        if name in KEEP or name in missing:
            continue
        path = ICONS / f"{name}.png"
        if not path.exists():
            continue
        old = QtGui.QImage(str(path))
        size = old.width() if old.width() > 0 else 512
        img = draw(code, size)
        tiles.append((name, img))
        if dry:
            continue
        if not (BACKUP / path.name).exists():
            shutil.copy2(path, BACKUP / path.name)
        img.save(str(path))
        done += 1
    if sheet:
        cell, cols = 110, 10
        rows = (len(tiles) + cols - 1) // cols
        out = QtGui.QImage(cols * cell, rows * cell, QtGui.QImage.Format.Format_ARGB32)
        out.fill(QtGui.QColor(36, 26, 52))
        pp = QtGui.QPainter(out)
        pp.setPen(QtGui.QColor(255, 194, 226))
        pp.setFont(QtGui.QFont("Segoe UI", 7))
        for i, (n, im) in enumerate(tiles):
            x, y = (i % cols) * cell, (i // cols) * cell
            pp.drawImage(QtCore.QRect(x + 25, y + 4, 60, 60), im)
            pp.drawText(QtCore.QRect(x, y + 70, cell, 30), QtCore.Qt.AlignmentFlag.AlignHCenter, n)
        pp.end()
        out.save(str(sheet))
    print(f"{'(Probelauf) ' if dry else ''}{done if not dry else len(tiles)} Symbole gezeichnet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
