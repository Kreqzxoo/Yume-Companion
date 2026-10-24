"""Yume look & feel helpers: sakura petal overlay, glyph icons and the grouped settings navigation."""
import math
import random

from PyQt6 import QtCore, QtGui, QtWidgets

ACCENT = "#FF8FC7"
ACCENT_SOFT = "#FFC2E2"


def glyph_icon(char, color=ACCENT, size=18):
    """Draws a single (symbol-font) character as a crisp, accent-coloured icon."""
    pm = QtGui.QPixmap(size * 2, size * 2)
    pm.fill(QtCore.Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
    font = QtGui.QFont("Segoe UI Symbol")
    font.setPixelSize(int(size * 1.5))
    p.setFont(font)
    p.setPen(QtGui.QColor(color))
    p.drawText(pm.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, char)
    p.end()
    pm.setDevicePixelRatio(2.0)
    return QtGui.QIcon(pm)


class SakuraLayer(QtWidgets.QWidget):
    """Very subtle, slowly drifting sakura petals and sparkles painted over the window (click-through)."""

    def __init__(self, parent, count=14):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._rng = random.Random(7)
        self._petals = [self._new_petal(initial=True) for _ in range(count)]
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self._t = 0.0
        parent.installEventFilter(self)
        self._fit()

    def eventFilter(self, obj, event):
        if event.type() in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Show):
            self._fit()
        return False

    def _fit(self):
        p = self.parentWidget()
        if p is not None:
            self.setGeometry(p.rect())
            self.raise_()

    def set_active(self, on):
        self.setVisible(bool(on))
        if on:
            self._timer.start()
            self._fit()
        else:
            self._timer.stop()

    def _new_petal(self, initial=False):
        r = self._rng
        return {
            "x": r.random(), "y": r.random() if initial else -0.05,
            "size": r.uniform(5, 11), "speed": r.uniform(0.012, 0.03),
            "drift": r.uniform(0.004, 0.012), "phase": r.uniform(0, 6.28),
            "rot": r.uniform(0, 360), "spin": r.uniform(-40, 40),
            "alpha": r.uniform(0.14, 0.30), "kind": r.choice(("petal", "petal", "petal", "spark")),
        }

    def _tick(self):
        dt = 0.04
        self._t += dt
        for i, pt in enumerate(self._petals):
            pt["y"] += pt["speed"] * dt * 3
            pt["x"] += math.sin(self._t * 0.8 + pt["phase"]) * pt["drift"] * dt * 3
            pt["rot"] += pt["spin"] * dt
            if pt["y"] > 1.05 or pt["x"] < -0.05 or pt["x"] > 1.05:
                self._petals[i] = self._new_petal()
        self.update()

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        for pt in self._petals:
            p.save()
            p.translate(pt["x"] * w, pt["y"] * h)
            p.rotate(pt["rot"])
            s = pt["size"]
            c = QtGui.QColor(255, 170, 210) if pt["kind"] == "petal" else QtGui.QColor(255, 235, 245)
            c.setAlphaF(pt["alpha"])
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(c)
            if pt["kind"] == "petal":
                path = QtGui.QPainterPath()
                path.moveTo(0, -s)
                path.cubicTo(s * 0.9, -s * 0.6, s * 0.7, s * 0.6, 0, s)
                path.cubicTo(-s * 0.7, s * 0.6, -s * 0.9, -s * 0.6, 0, -s)
                p.drawPath(path)
            else:
                path = QtGui.QPainterPath()
                path.moveTo(0, -s * 0.8)
                path.quadTo(0, 0, s * 0.8, 0)
                path.quadTo(0, 0, 0, s * 0.8)
                path.quadTo(0, 0, -s * 0.8, 0)
                path.quadTo(0, 0, 0, -s * 0.8)
                p.drawPath(path)
            p.restore()
        p.end()


class SettingsNavHelper(QtCore.QObject):
    """Grouped settings navigation: search box, group headers and stack-index mapping."""

    def __init__(self, menu, stack, sidebar_layout, translations):
        super().__init__(menu)
        self.menu = menu
        self.stack = stack
        self._tr = translations
        self._busy = False

        self.menu.setIconSize(QtCore.QSize(18, 18))
        self.menu.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.menu.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.menu.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        self.menu.setWordWrap(False)
        self.menu.setStyleSheet(
            "QListWidget#options_menu { background: transparent; border: none; outline: none; }"
            "QListWidget#options_menu::item { color: #B9A9C9; font-family: 'Inter Tight SemiBold'; font-size: 13px;"
            " padding: 6px 12px; border-radius: 10px; margin: 0px 0px; border: 1px solid transparent; }"
            "QListWidget#options_menu::item:hover { background-color: rgba(255,143,199,0.10); color: #FFFFFF; }"
            "QListWidget#options_menu::item:selected { background-color: rgba(255,143,199,0.18);"
            " border: 1px solid rgba(255,143,199,0.45); color: #FFFFFF; }"
            "QListWidget#options_menu QScrollBar:vertical { width: 6px; background: transparent; margin: 0; }"
            "QListWidget#options_menu QScrollBar::handle:vertical { background: rgba(255,143,199,0.35); border-radius: 3px; min-height: 24px; }"
            "QListWidget#options_menu QScrollBar::add-line:vertical, QListWidget#options_menu QScrollBar::sub-line:vertical { height: 0; }"
            "QListWidget#options_menu::item:disabled { color: #8D7AA3; font-size: 10px; padding: 10px 12px 2px 12px;"
            " background: transparent; border: none; }"
        )

        self.search = QtWidgets.QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText(self._t("settings_search_placeholder", "Search settings..."))
        self.search.setStyleSheet(
            "QLineEdit { background-color: rgba(255,255,255,0.05); border: 1px solid rgba(255,143,199,0.25);"
            " border-radius: 12px; padding: 7px 12px; color: #F1E8F6; margin: 0px 6px 8px 6px; }"
            "QLineEdit:focus { border: 1px solid rgba(255,143,199,0.7); background-color: rgba(255,143,199,0.08); }"
        )
        # search box sits right below the title label (index 0 of the sidebar layout)
        sidebar_layout.insertWidget(1, self.search)
        self.search.textChanged.connect(self._filter)

        self.menu.currentItemChanged.connect(self._on_current_changed)

    def _t(self, key, fallback):
        return self._tr.get(key, fallback) if hasattr(self._tr, "get") else fallback

    def retranslate(self, translations):
        self._tr = translations
        self.search.setPlaceholderText(self._t("settings_search_placeholder", "Search settings..."))

    def _scroll_to_top(self):
        page = self.stack.currentWidget()
        area = page.findChild(QtWidgets.QScrollArea) if page is not None else None
        if area is not None:
            area.verticalScrollBar().setValue(0)

    def select_tab(self, stack_index):
        if stack_index == 1:           # "APIs & Providers" was merged into the language-model page
            stack_index = 2
        for row in range(self.menu.count()):
            item = self.menu.item(row)
            if item.data(QtCore.Qt.ItemDataRole.UserRole) == stack_index:
                self.search.clear()
                self.menu.setCurrentRow(row)
                self.stack.setCurrentIndex(stack_index)
                self._scroll_to_top()
                return
        self.stack.setCurrentIndex(stack_index)
        self._scroll_to_top()

    def _on_current_changed(self, current, _previous):
        if current is None:
            return
        idx = current.data(QtCore.Qt.ItemDataRole.UserRole)
        if idx is not None:
            self.stack.setCurrentIndex(idx)
            self._scroll_to_top()

    def _filter(self, text):
        needle = text.strip().lower()
        group_has_match = None
        # walk bottom-up so a header is shown only if one of its entries matches
        for row in range(self.menu.count() - 1, -1, -1):
            item = self.menu.item(row)
            if item.data(QtCore.Qt.ItemDataRole.UserRole) is None:
                item.setHidden(bool(needle) and not group_has_match)
                group_has_match = False
            else:
                match = (not needle) or needle in item.text().lower()
                item.setHidden(not match)
                group_has_match = bool(group_has_match) or match
        if needle:
            for row in range(self.menu.count()):
                item = self.menu.item(row)
                if not item.isHidden() and item.data(QtCore.Qt.ItemDataRole.UserRole) is not None:
                    self.menu.setCurrentRow(row)
                    break


UNIFIED_PX = 13


def _unify_font(widget, px=UNIFIED_PX):
    f = widget.font()
    if f.pixelSize() != px:
        f.setPixelSize(px)
        widget.setFont(f)
    # the global style sheet sets its own size for check boxes, so a widget level rule is needed as well
    if isinstance(widget, (QtWidgets.QCheckBox, QtWidgets.QRadioButton)) and not widget.property("yume_font_unified"):
        widget.setProperty("yume_font_unified", True)
        cls = type(widget).__name__ if type(widget).__name__.startswith("Q") else "QCheckBox"
        base = "QRadioButton" if isinstance(widget, QtWidgets.QRadioButton) else "QCheckBox"
        widget.setStyleSheet(widget.styleSheet() + f" {base} {{ font-size: {px}px; }}")


def fit_settings_pages(stack):
    """Make the settings pages uniform and let them shrink with the window:
    one text size for labels / inputs / buttons / checkboxes, long labels wrap, form rows wrap below their label,
    buttons / checkboxes / combos may be narrower than their text."""
    for i in range(stack.count()):
        page = stack.widget(i)
        for area in page.findChildren(QtWidgets.QScrollArea):
            area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        form_labels = set()
        for form in page.findChildren(QtWidgets.QFormLayout):
            form.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapLongRows)
            for r in range(form.rowCount()):
                item = form.itemAt(r, QtWidgets.QFormLayout.ItemRole.LabelRole)
                if item is not None and item.widget() is not None:
                    form_labels.add(item.widget())
        for grid in page.findChildren(QtWidgets.QGridLayout):       # card grids: let each card shrink with its wrapped text
            for k in range(grid.count()):
                cw = grid.itemAt(k).widget()
                if cw is not None and cw.minimumWidth() == 0:
                    cw.setMinimumWidth(1)
        for label in page.findChildren(QtWidgets.QLabel):
            if label.pixmap().isNull() and label.font().family().startswith("Comfortaa") and 11 < label.font().pixelSize() <= 16:
                _unify_font(label)
            if label not in form_labels and not label.wordWrap() and len(label.text()) > 22 and label.pixmap().isNull():
                label.setWordWrap(True)
        for cb in page.findChildren(QtWidgets.QCheckBox):
            if cb.font().family().startswith("Comfortaa") and cb.minimumHeight() < 30:
                _unify_font(cb)
        for btn in page.findChildren(QtWidgets.QAbstractButton):
            if btn.text():
                if btn.minimumWidth() == 0:
                    btn.setMinimumWidth(1)
                if btn.font().family().startswith("Comfortaa") and btn.font().pixelSize() in (-1, 12, 13, 14, 15):
                    _unify_font(btn)
        for combo in page.findChildren(QtWidgets.QComboBox):
            combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(6)
            if combo.minimumWidth() == 0:
                combo.setMinimumWidth(1)
            _unify_font(combo)
        for cls in (QtWidgets.QLineEdit, QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox):
            for w in page.findChildren(cls):
                _unify_font(w)
