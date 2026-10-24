"""Welcome hero for the empty start page: animated round logo, greeting by time of day and three quick-start steps."""
from __future__ import annotations

import datetime
import math
import random

from PyQt6 import QtCore, QtGui, QtWidgets

PINK = QtGui.QColor(255, 143, 199)
LAV = QtGui.QColor(182, 156, 255)


class LogoBadge(QtWidgets.QWidget):
    """Round app icon with a breathing glow, orbiting sparkles and a soft ring."""

    def __init__(self, pixmap: QtGui.QPixmap, size: int = 190, parent=None):
        super().__init__(parent)
        self.setFixedSize(size + 90, size + 90)
        self._size = size
        self._t = 0.0
        rng = random.Random(3)
        self._sparks = [(rng.uniform(0, 6.28), rng.uniform(0.35, 0.9), rng.uniform(2.5, 5.0), rng.uniform(0.5, 1.4)) for _ in range(9)]
        self._pm = self._round(pixmap, size)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    @staticmethod
    def _round(src: QtGui.QPixmap, size: int) -> QtGui.QPixmap:
        out = QtGui.QPixmap(size * 2, size * 2)
        out.fill(QtCore.Qt.GlobalColor.transparent)
        p = QtGui.QPainter(out)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        back = QtGui.QLinearGradient(0, 0, 0, size * 2)
        back.setColorAt(0, QtGui.QColor(46, 28, 62))
        back.setColorAt(1, QtGui.QColor(24, 14, 38))
        p.setBrush(back)
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, size * 2, size * 2)
        if not src.isNull():
            # cut the circle inside the art: the icon has transparent margins and a glow
            img = src.toImage()
            bbox = QtCore.QRect(0, 0, img.width(), img.height())
            minx, miny, maxx, maxy = img.width(), img.height(), -1, -1
            step = max(1, img.width() // 128)
            for y in range(0, img.height(), step):
                for x in range(0, img.width(), step):
                    if QtGui.qAlpha(img.pixel(x, y)) > 170:
                        minx, maxx = min(minx, x), max(maxx, x)
                        miny, maxy = min(miny, y), max(maxy, y)
            if maxx > minx and maxy > miny:
                bbox = QtCore.QRect(minx, miny, maxx - minx, maxy - miny)
            side = int(min(bbox.width(), bbox.height()) * 0.985)
            sx = bbox.x() + (bbox.width() - side) // 2
            sy = bbox.y() + (bbox.height() - side) // 2 + int(bbox.height() * 0.025)
            path = QtGui.QPainterPath()
            path.addEllipse(0, 0, size * 2, size * 2)
            p.setClipPath(path)
            p.drawPixmap(QtCore.QRect(0, 0, size * 2, size * 2), src, QtCore.QRect(sx, sy, side, side))
        p.end()
        out.setDevicePixelRatio(2.0)
        return out

    def _tick(self):
        self._t += 0.033
        self.update()

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2 + math.sin(self._t * 1.6) * 3
        r = self._size / 2
        pulse = 1 + math.sin(self._t * 1.4) * 0.06
        glow = QtGui.QRadialGradient(cx, cy, r * 1.55 * pulse)
        glow.setColorAt(0.55, QtGui.QColor(255, 143, 199, 90))
        glow.setColorAt(1, QtGui.QColor(255, 143, 199, 0))
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QtCore.QPointF(cx, cy), r * 1.55 * pulse, r * 1.55 * pulse)
        ring = QtGui.QPen(QtGui.QColor(255, 160, 210, int(110 + 60 * math.sin(self._t * 2))), 3)
        p.setPen(ring)
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        p.drawEllipse(QtCore.QPointF(cx, cy), r + 8, r + 8)
        p.drawPixmap(QtCore.QRectF(cx - r, cy - r, self._size, self._size).toRect(), self._pm)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 200, 230, 210), 2))
        p.drawEllipse(QtCore.QPointF(cx, cy), r, r)
        # orbiting sparkles
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        for phase, radius, size, speed in self._sparks:
            ang = phase + self._t * speed * 0.6
            rr = r * (1.12 + radius * 0.38)
            x, y = cx + math.cos(ang) * rr, cy + math.sin(ang) * rr * 0.9
            a = int(120 + 120 * abs(math.sin(self._t * 2 + phase)))
            p.setBrush(QtGui.QColor(255, 225, 242, a))
            star = QtGui.QPainterPath()
            for i in range(8):
                rad = size * (1 if i % 2 == 0 else 0.3)
                th = -math.pi / 2 + i * math.pi / 4
                pt = QtCore.QPointF(x + math.cos(th) * rad, y + math.sin(th) * rad)
                star.moveTo(pt) if i == 0 else star.lineTo(pt)
            star.closeSubpath()
            p.drawPath(star)


class StepCard(QtWidgets.QFrame):
    clicked = QtCore.pyqtSignal()

    def __init__(self, number, title, text, button_text, parent=None):
        super().__init__(parent)
        self.setObjectName("stepCard")
        self.setStyleSheet(
            "QFrame#stepCard { background: rgba(255,143,199,0.06); border: 1px solid rgba(255,143,199,0.24); border-radius: 16px; }"
            "QFrame#stepCard:hover { background: rgba(255,143,199,0.11); border-color: rgba(255,143,199,0.5); }"
            "QLabel { background: transparent; border: none; }")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(8)
        head = QtWidgets.QHBoxLayout()
        num = QtWidgets.QLabel(str(number))
        num.setFixedSize(30, 30)
        num.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        num.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #FF8FC7, stop:1 #B69CFF); color: #1b1226; "
                          "font-weight: 800; border-radius: 15px;")
        t = QtWidgets.QLabel(title)
        t.setStyleSheet("color: #F6EAF6; font-size: 16px; font-weight: 600;")
        head.addWidget(num)
        head.addWidget(t, 1)
        lay.addLayout(head)
        d = QtWidgets.QLabel(text)
        d.setWordWrap(True)
        d.setStyleSheet("color: #BFAFD0; font-size: 12.5px;")
        lay.addWidget(d, 1)
        btn = QtWidgets.QPushButton(button_text)
        btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        btn.setFixedHeight(36)
        btn.setStyleSheet("QPushButton { background: rgba(255,143,199,0.16); color: #F6EAF6; border: 1px solid rgba(255,143,199,0.5); "
                          "border-radius: 10px; font-weight: 600; } QPushButton:hover { background: rgba(255,143,199,0.3); }")
        btn.clicked.connect(self.clicked.emit)
        lay.addWidget(btn)


def _greeting(tr):
    h = datetime.datetime.now().hour
    if 5 <= h < 11:
        return tr("home_greet_morning", "Good morning")
    if 11 <= h < 17:
        return tr("home_greet_day", "Hello")
    if 17 <= h < 22:
        return tr("home_greet_evening", "Good evening")
    return tr("home_greet_night", "Good night")


class HomeWelcome(QtWidgets.QWidget):
    def __init__(self, ui, translations, parent=None):
        super().__init__(parent)
        self.ui = ui
        tr = translations.get
        self.setStyleSheet("background: transparent;")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(30, 10, 30, 20)
        outer.addStretch(1)

        try:
            from app.utils.branding import build_app_icon, app_name
            pix = build_app_icon().pixmap(512, 512)
            name = app_name()
        except Exception:
            pix, name = QtGui.QPixmap(), "Yume Companion"
        badge = LogoBadge(pix)
        outer.addWidget(badge, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)

        self.greet = QtWidgets.QLabel(f"{_greeting(tr)}! ♡")
        self.greet.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.greet.setStyleSheet("color: #FFC2E2; font-size: 15px; letter-spacing: 1px;")
        title = QtWidgets.QLabel(tr("home_welcome_title", "Welcome to {name}").format(name=name))
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #F6EAF6; font-size: 30px; font-weight: 700;")
        sub = QtWidgets.QLabel(tr("home_welcome_sub", "Three small steps and your companion is ready."))
        sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #BFAFD0; font-size: 14px;")
        for w in (self.greet, title, sub):
            outer.addWidget(w)
        outer.addSpacing(18)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(16)
        cards = [
            (1, tr("home_step1_title", "Choose a model"), tr("home_step1_text", "Pick a local model or connect an online provider."),
             tr("home_step1_btn", "Open settings"), self._open_models),
            (2, tr("home_step2_title", "Create a character"), tr("home_step2_text", "Describe personality and look - or let the AI helper do it."),
             tr("home_step2_btn", "Create character"), self._create_character),
            (3, tr("home_step3_title", "Or discover one"), tr("home_step3_text", "Import cards or browse the gateway for ready-made characters."),
             tr("home_step3_btn", "Open gateway"), self._open_gateway),
        ]
        for n, t, d, b, fn in cards:
            card = StepCard(n, t, d, b)
            card.setMinimumHeight(170)
            card.clicked.connect(fn)
            row.addWidget(card, 1)
        wrap = QtWidgets.QWidget()
        wrap.setLayout(row)
        wrap.setMaximumWidth(900)
        outer.addWidget(wrap, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        outer.addSpacing(14)
        tip = QtWidgets.QLabel(tr("home_tip", "Tip: the dashboard in the settings shows speed and resource usage while you chat."))
        tip.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        tip.setStyleSheet("color: #8D7AA3; font-size: 12px;")
        outer.addWidget(tip)
        outer.addStretch(2)

    def _open_models(self):
        self.ui.pushButton_options.click()
        QtCore.QTimer.singleShot(0, lambda: self.ui.select_option_tab(2))

    def _create_character(self):
        self.ui.pushButton_create_character_2.click()

    def _open_gateway(self):
        self.ui.pushButton_characters_gateway.click()


def install_home_welcome(main_window):
    """Hides the old empty-state widgets and puts the welcome hero into the page."""
    ui = main_window.ui
    page = ui.main_no_characters_page
    for name in ("frame_main_button", "main_no_characters_description_label", "main_no_characters_advice_label"):
        w = getattr(ui, name, None)
        if w is not None:
            w.hide()
    hero = HomeWelcome(ui, main_window.translations, page)
    ui.gridLayout_7.addWidget(hero, 0, 0, 7, 1)
    ui.home_welcome = hero
    return hero
