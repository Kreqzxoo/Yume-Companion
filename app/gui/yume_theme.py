"""Yume look ("Dusk Glass"): one place for the colours, shapes and navigation style of the program.

* TOKENS      - the palette (surfaces, text, accents) used by new code and by the filter below.
* filter_qss  - every style sheet of the program passes through it (hook on QWidget.setStyleSheet): old neutral greys / blues become the
                Yume palette, translucent whites become lavender glass (corner radii are left alone: Qt draws round badges wrongly when the radius exceeds half the size). The program's logic is not touched.
* install_hook() must run BEFORE the main window is built, restyle_window() after it (navigation rail, title bar, global details).
"""
from __future__ import annotations

import logging
import re

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger("YumeTheme")

TOKENS = {
    "ink": "#130F1E", "surface": "#181222", "card_top": "#241A36", "card_bottom": "#1A1328", "line": "rgba(226,214,255,0.10)",
    "text": "#F1E8F6", "text_dim": "#B9A9D0", "text_faint": "#8D7AA3",
    "pink": "#FF8FC7", "pink_soft": "#FFC2E2", "violet": "#B69CFF", "violet_soft": "#D3C2FF", "mint": "#7EE8C7", "rose": "#FF7A93", "amber": "#F6C177",
}
MARK = "/*yume*/"

# old colours -> Yume palette (hex, case-insensitive)
_COLORS = {
    "#E0E0E0": "#EBE3F7", "#E2E8F0": "#EBE3F7", "#DEDAD2": "#E6DFF2", "#D4D4D4": "#DCD2EC", "#CCCCCC": "#D2C7E4", "#BBBBBB": "#BFB2D6",
    "#A0A0A0": "#A99BC4", "#9CA3AF": "#A99BC4", "#6F6B63": "#7D7194", "#888888": "#8D7AA3",
    "#3B82F6": "#B69CFF", "#2563EB": "#9B7BFF", "#60A5FA": "#C9B3FF", "#82CDFF": "#D3C2FF", "#4BB8FF": "#C9B3FF",
    "#4ADE80": "#7EE8C7", "#6FCF97": "#7EE8C7",
    "#0F0F15": "#140E22", "#08080A": "#110B1E", "#0C0C10": "#130D21", "#16161E": "#1B1330", "#1A1A22": "#1E1532", "#121218": "#171024",
    "#F87171": "#FF7A93", "#C44040": "#D9455F", "#FF6B6B": "#FF7A93", "#EE7777": "#FF8CA3",
}
_COLOR_RE = re.compile("|".join(re.escape(k) for k in _COLORS), re.I)
_WHITE_RE = re.compile(r"rgba\(\s*255\s*,\s*255\s*,\s*255\s*,\s*([0-9.]+)\s*\)", re.I)
_GREY_RGB_RE = re.compile(r"rgb\(\s*(\d{2,3})\s*,\s*\1\s*,\s*\1\s*\)")


_COLD_RE = re.compile(r"rgb\(\s*(\d{1,2})\s*,\s*\1\s*,\s*(\d{1,2})\s*\)")


def _cold(m: re.Match) -> str:
    """Bluish near-blacks (26,26,34) become the plum of the Yume surfaces."""
    r, b = int(m.group(1)), int(m.group(2))
    if b - r < 4 or b - r > 16 or b > 60:
        return m.group(0)
    return f"rgb({r + 5}, {max(0, r - 3)}, {b + 14})"


def _grey(m: re.Match) -> str:
    """rgb(g, g, g) -> the same brightness with a slight lavender cast (only mid / light greys; the dark surfaces are already Yume's)."""
    g = int(m.group(1))
    if g < 60 or g > 240:
        return m.group(0)
    return f"rgb({min(255, g + 4)}, {min(255, g)}, {min(255, g + 14)})"


def _transform(s: str) -> str:
    s = _COLOR_RE.sub(lambda m: _COLORS[m.group(0).upper()], s)
    s = _WHITE_RE.sub(lambda m: f"rgba(226,214,255,{m.group(1)})", s)
    s = _GREY_RGB_RE.sub(_grey, s)
    s = _COLD_RE.sub(_cold, s)
    return s


def filter_qss(s: str) -> str:
    """Idempotent: the part that already went through the filter is marked and not touched again."""
    if not s or not isinstance(s, str):
        return s
    if MARK in s:
        head, _, tail = s.rpartition(MARK)
        return head + MARK + ((_transform(tail) + MARK) if tail.strip() else "")
    return _transform(s) + MARK


def _app_qss(s: str) -> str:
    """Application-wide style: filtered, plus the Yume basics (scroll bars, tooltips, menus) exactly once."""
    s = filter_qss(s or "")
    return s if "yume-global" in s else s + chr(10) + "/*yume-global*/" + GLOBAL_QSS


_hooked = False


def install_hook():
    """Routes every setStyleSheet of widgets and of the application through filter_qss."""
    global _hooked
    if _hooked:
        return
    try:
        orig_w = QtWidgets.QWidget.setStyleSheet
        QtWidgets.QWidget.setStyleSheet = lambda self, s: orig_w(self, filter_qss(s))
        orig_a = QtWidgets.QApplication.setStyleSheet
        QtWidgets.QApplication.setStyleSheet = lambda self, s: orig_a(self, _app_qss(s))
        _hooked = True
    except Exception:
        logger.exception("Style hook could not be installed")


def refilter_all():
    """Widgets that were built before the hook (or by Qt itself) get the filter once."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    for w in app.allWidgets():
        try:
            ss = w.styleSheet()
            if ss and not ss.rstrip().endswith(MARK):
                w.setStyleSheet(ss)
        except Exception:
            pass


# ------------------------------------------------------------------ icons
def tinted_icon(path: str, normal: str = "#B9A9D0", active: str = "#FF8FC7", size: int = 64) -> QtGui.QIcon:
    """Icon from a (white / lavender) PNG in two colours: normal and 'checked' (active)."""
    src = QtGui.QPixmap(path)
    if src.isNull():
        return QtGui.QIcon()
    src = src.scaled(size, size, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)

    def tint(color: str) -> QtGui.QPixmap:
        out = QtGui.QPixmap(src.size())
        out.fill(QtCore.Qt.GlobalColor.transparent)
        p = QtGui.QPainter(out)
        p.drawPixmap(0, 0, src)
        p.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
        p.fillRect(out.rect(), QtGui.QColor(color))
        p.end()
        return out

    icon = QtGui.QIcon()
    n, a = tint(normal), tint(active)
    icon.addPixmap(n, QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
    icon.addPixmap(a, QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.On)
    icon.addPixmap(a, QtGui.QIcon.Mode.Active, QtGui.QIcon.State.Off)
    icon.addPixmap(a, QtGui.QIcon.Mode.Active, QtGui.QIcon.State.On)
    return icon


# ------------------------------------------------------------------ navigation rail
RAIL_ITEMS = (("pushButton_main", "main"), ("pushButton_soul_stage", "soul_stage"), ("pushButton_rp_editors", "rp_editors"),
              ("pushButton_characters_gateway", "gateway"), ("pushButton_models_hub", "modelshub"), ("pushButton_options", "options"))

RAIL_BUTTON_QSS = """
QPushButton {
    color: #B9A9D0; background: transparent; border: 1px solid transparent; border-radius: 14px;
    text-align: left; padding: 0px 8px 0px 12px; margin: 2px 9px; min-height: 42px; max-height: 42px;
}
QPushButton:hover { background: rgba(226,214,255,0.07); color: #F1E8F6; }
QPushButton:pressed { background: rgba(226,214,255,0.11); color: #FFFFFF; }
QPushButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(255,143,199,0.26), stop:1 rgba(182,156,255,0.12));
    border: 1px solid rgba(255,143,199,0.34); color: #FFFFFF;
}
"""
RAIL_BG_QSS = """
#SideBar_Left {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1D1433, stop:0.55 #160F27, stop:1 #110B1E);
    border-right: 1px solid rgba(226,214,255,0.08);
}
"""


GLOBAL_QSS = """
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px 0px; }
QScrollBar::handle:vertical { background: rgba(182,156,255,0.28); border-radius: 4px; min-height: 36px; }
QScrollBar::handle:vertical:hover { background: rgba(255,143,199,0.55); }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 0px 2px; }
QScrollBar::handle:horizontal { background: rgba(182,156,255,0.28); border-radius: 4px; min-width: 36px; }
QScrollBar::handle:horizontal:hover { background: rgba(255,143,199,0.55); }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { background: none; border: none; width: 0px; height: 0px; }
QToolTip { background-color: #1E1530; color: #F1E8F6; border: 1px solid rgba(255,143,199,0.35); border-radius: 8px; padding: 6px 10px; }
QMenu { background-color: #1B1330; color: #F1E8F6; border: 1px solid rgba(214,190,255,0.16); border-radius: 10px; padding: 6px; }
QMenu::item { padding: 7px 18px; border-radius: 7px; }
QMenu::item:selected { background-color: rgba(255,143,199,0.22); }
"""


def restyle_window(window):
    """Navigation rail, title bar and a few global details. Safe to call once after the main window exists."""
    ui = getattr(window, "ui", None)
    if ui is None:
        return
    try:
        if hasattr(ui, "SideBar_Left"):
            ui.SideBar_Left.setStyleSheet(RAIL_BG_QSS)
        for btn_name, icon_name in RAIL_ITEMS:
            btn = getattr(ui, btn_name, None)
            if btn is None:
                continue
            btn.setIcon(tinted_icon(f"app/gui/icons/{icon_name}.png"))
            btn.setIconSize(QtCore.QSize(20, 20))
    except Exception:
        logger.exception("Navigation rail could not be restyled")
    try:
        mb = getattr(ui, "menu_bar", None)
        if mb is not None:
            mb.setStyleSheet("#menu_bar { background-color: #130D21; border-bottom: 1px solid rgba(226,214,255,0.06); }")
        for name in ("minimize_btn", "maximize_btn"):
            b = getattr(ui, name, None)
            if b is not None:
                b.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 0px; } "
                                "QPushButton:hover { background: rgba(226,214,255,0.10); } QPushButton:pressed { background: rgba(226,214,255,0.16); }")
    except Exception:
        logger.exception("Title bar could not be restyled")
    try:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.setStyleSheet(app.styleSheet())          # the hook adds the global basics
    except Exception:
        logger.exception("Global style could not be applied")
    refilter_all()
