"""Settings page 'Spotify': Client ID, login, now playing + player buttons. The login is shared with the phone (Android Connector)."""
from __future__ import annotations

import logging
import threading
import webbrowser

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger("SpotifySettings")

DEV_URL = "https://developer.spotify.com/dashboard"
BTN_STYLE = ("QPushButton { background: rgba(255,255,255,0.045); color:#e0e0e0; border:1px solid rgba(255,255,255,0.13); "
             "border-radius:8px; padding:4px 12px; } QPushButton:hover { background: rgba(255,143,199,0.14); "
             "border-color: rgba(255,143,199,0.5); } QPushButton:disabled { color: rgba(255,255,255,0.3); }")


def build_spotify_page(ui, create_scroll_page, create_glass_card, font_input):
    from app.utils import spotify_pc
    tr = ui.translations.get
    page, layout = create_scroll_page()
    page.setObjectName("spotify_tab")

    card, l = create_glass_card(tr("spotify_title", "Spotify"))
    intro = QtWidgets.QLabel(tr(
        "spotify_intro",
        "Connect your own Spotify app once (no password and no secret are stored here). Yume can then start music, pause, skip and tell "
        "what is playing - on the PC dashboard and on the phone. The login is handed to the paired phone automatically, so you only log in once. "
        "Playback control needs Spotify Premium."))
    intro.setWordWrap(True)
    intro.setStyleSheet("color: rgba(220, 220, 230, 0.78); border: none; background: transparent;")
    l.addWidget(intro)

    import re
    steps = QtWidgets.QLabel(re.sub(r"\s+(?=[23]\. )", "\n", tr(
        "spotify_steps",
        "1. Open the Spotify developer dashboard and create an app.\n"
        "2. Add the redirect URI shown below to that app (Settings > Redirect URIs) and for the phone also  yume://spotify .\n"
        "3. Paste the Client ID of the app here and click \"Log in\".")))
    steps.setWordWrap(True)
    steps.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(steps)

    form = QtWidgets.QFormLayout()
    form.setHorizontalSpacing(22)
    ui.lineEdit_spotify_client = QtWidgets.QLineEdit()
    ui.lineEdit_spotify_client.setFixedHeight(38)
    ui.lineEdit_spotify_client.setFont(font_input)
    ui.lineEdit_spotify_client.setPlaceholderText("Client ID")
    form.addRow(tr("spotify_client_label", "Client ID"), ui.lineEdit_spotify_client)
    ui.lineEdit_spotify_redirect = QtWidgets.QLineEdit(spotify_pc.REDIRECT_URI)
    ui.lineEdit_spotify_redirect.setReadOnly(True)
    ui.lineEdit_spotify_redirect.setFixedHeight(38)
    ui.lineEdit_spotify_redirect.setFont(font_input)
    form.addRow(tr("spotify_redirect_label", "Redirect URI (PC)"), ui.lineEdit_spotify_redirect)
    l.addLayout(form)

    row = QtWidgets.QHBoxLayout()
    ui.pushButton_spotify_login = QtWidgets.QPushButton(tr("spotify_login", "Log in"))
    ui.pushButton_spotify_logout = QtWidgets.QPushButton(tr("spotify_logout", "Log out"))
    ui.pushButton_spotify_dev = QtWidgets.QPushButton(tr("spotify_open_dev", "Spotify developer page"))
    ui.pushButton_spotify_copy = QtWidgets.QPushButton(tr("spotify_copy_redirect", "Copy redirect URI"))
    for b in (ui.pushButton_spotify_login, ui.pushButton_spotify_logout, ui.pushButton_spotify_dev, ui.pushButton_spotify_copy):
        b.setFont(font_input)
        b.setFixedHeight(38)
        b.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        b.setStyleSheet(BTN_STYLE)
        row.addWidget(b)
    l.addLayout(row)

    ui.label_spotify_status = QtWidgets.QLabel("")
    ui.label_spotify_status.setWordWrap(True)
    ui.label_spotify_status.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(ui.label_spotify_status)
    layout.addWidget(card)

    pcard, pl = create_glass_card(tr("spotify_player_title", "Now playing"))
    ui.label_spotify_now = QtWidgets.QLabel("-")
    ui.label_spotify_now.setWordWrap(True)
    ui.label_spotify_now.setStyleSheet("color: #ffffff; font-size: 15px; border: none; background: transparent;")
    pl.addWidget(ui.label_spotify_now)
    prow = QtWidgets.QHBoxLayout()
    ui.pushButton_spotify_prev = QtWidgets.QPushButton(tr("spotify_prev", "Previous"))
    ui.pushButton_spotify_toggle = QtWidgets.QPushButton(tr("spotify_toggle", "Play / Pause"))
    ui.pushButton_spotify_next = QtWidgets.QPushButton(tr("spotify_next", "Next"))
    for b in (ui.pushButton_spotify_prev, ui.pushButton_spotify_toggle, ui.pushButton_spotify_next):
        b.setFont(font_input)
        b.setFixedHeight(38)
        b.setStyleSheet(BTN_STYLE)
        prow.addWidget(b)
    pl.addLayout(prow)
    ui.slider_spotify_volume = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
    ui.slider_spotify_volume.setRange(0, 100)
    pl.addWidget(ui.slider_spotify_volume)
    layout.addWidget(pcard)
    layout.addStretch()

    ui.spotify_controller = SpotifyController(ui)
    return page


class SpotifyController(QtCore.QObject):
    result = QtCore.pyqtSignal(str, object)

    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.signals = None
        self._playing = False
        self._busy = False
        self.result.connect(self._on_result)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(4000)
        self.timer.timeout.connect(self.refresh)
        ui.pushButton_spotify_login.clicked.connect(self.login)
        ui.pushButton_spotify_logout.clicked.connect(self.logout)
        ui.pushButton_spotify_dev.clicked.connect(lambda: webbrowser.open(DEV_URL))
        ui.pushButton_spotify_copy.clicked.connect(self._copy)
        ui.pushButton_spotify_prev.clicked.connect(lambda: self._control("previous"))
        ui.pushButton_spotify_next.clicked.connect(lambda: self._control("next"))
        ui.pushButton_spotify_toggle.clicked.connect(lambda: self._control("pause" if self._playing else "resume"))
        ui.slider_spotify_volume.sliderReleased.connect(lambda: self._control("volume", ui.slider_spotify_volume.value()))
        ui.lineEdit_spotify_client.editingFinished.connect(self._save_client)
        from app.utils import spotify_pc
        ui.lineEdit_spotify_client.setText(spotify_pc.client_id())
        self._show_state()
        self.timer.start()

    def attach(self, signals):
        self.signals = signals
        self.refresh()

    # ------------------------------------------------------------------ helpers
    def _bg(self, name, fn):
        def run():
            try:
                self.result.emit(name, fn())
            except Exception as exc:
                logger.debug("spotify %s failed: %s", name, exc)
                self.result.emit(name, exc)
        threading.Thread(target=run, daemon=True).start()

    def _status(self, text, color="#B9A9C9"):
        self.ui.label_spotify_status.setStyleSheet(f"color: {color}; border: none; background: transparent;")
        self.ui.label_spotify_status.setText(text)

    def _show_state(self):
        from app.utils import spotify_pc
        on = spotify_pc.connected()
        self.ui.pushButton_spotify_logout.setEnabled(on)
        for b in (self.ui.pushButton_spotify_prev, self.ui.pushButton_spotify_toggle, self.ui.pushButton_spotify_next, self.ui.slider_spotify_volume):
            b.setEnabled(on)
        if on:
            self._status(self.ui.translations.get("spotify_connected", "Connected to Spotify. The paired phone uses the same login."), "#8BE9A8")
        elif spotify_pc.status_text:
            self._status(spotify_pc.status_text)
        else:
            self._status(self.ui.translations.get("spotify_not_connected", "Not connected."))

    def _save_client(self):
        from app.utils import spotify_pc
        value = self.ui.lineEdit_spotify_client.text().strip()
        if value != spotify_pc.client_id():
            spotify_pc.set_client_id(value)
            self._show_state()

    def _copy(self):
        QtWidgets.QApplication.clipboard().setText(self.ui.lineEdit_spotify_redirect.text())
        self._status(self.ui.translations.get("spotify_redirect_copied", "Redirect URI copied."))

    # ------------------------------------------------------------------ actions
    def login(self):
        from app.utils import spotify_pc
        self._save_client()
        try:
            url = spotify_pc.start_login()
        except ValueError as exc:
            self._status(str(exc), "#F6C177")
            return
        webbrowser.open(url)
        self._status(spotify_pc.status_text)
        QtCore.QTimer.singleShot(3000, self._poll_login)

    def _poll_login(self):
        from app.utils import spotify_pc
        self._show_state()
        if not spotify_pc.connected() and spotify_pc.status_text.startswith("Warte"):
            QtCore.QTimer.singleShot(2000, self._poll_login)
        elif spotify_pc.connected():
            self.refresh()

    def logout(self):
        from app.utils import spotify_pc
        spotify_pc.logout()
        self.ui.label_spotify_now.setText("-")
        self._show_state()

    def _control(self, action, value=None):
        from app.utils import spotify_pc
        self._bg("control", lambda: spotify_pc.control(action, value))

    def refresh(self):
        from app.utils import spotify_pc
        if self._busy or not spotify_pc.connected() or not self.isVisibleHint():
            return
        self._busy = True
        self._bg("now", lambda: spotify_pc.now_playing(0))

    def isVisibleHint(self):
        try:
            return self.ui.lineEdit_spotify_client.isVisible()
        except Exception:
            return False

    def _on_result(self, name, data):
        if name == "now":
            self._busy = False
            if isinstance(data, Exception) or not isinstance(data, dict):
                return
            self._playing = bool(data.get("playing"))
            if data.get("error"):
                self.ui.label_spotify_now.setText(data["error"])
            elif data.get("title"):
                self.ui.label_spotify_now.setText(f"{data['title']}\n{data.get('artist', '')}  ·  {data.get('device', '')}")
                if data.get("volume") is not None and not self.ui.slider_spotify_volume.isSliderDown():
                    self.ui.slider_spotify_volume.setValue(int(data["volume"]))
            else:
                self.ui.label_spotify_now.setText(self.ui.translations.get("spotify_idle", "Nothing playing - start Spotify on the phone or PC once."))
        elif name == "control":
            if isinstance(data, tuple) and not data[0]:
                self._status(data[1], "#F6C177")
            QtCore.QTimer.singleShot(700, self.refresh)
