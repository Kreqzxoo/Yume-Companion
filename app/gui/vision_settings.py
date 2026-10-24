"""Settings page 'Vision' (sub-category of Local LLM): enable, pick/download a vision
model, test it. GPU/device selection lives with the other GPU choices on the
'AI Services' page (shown here as a read-only summary)."""
from __future__ import annotations

import logging
import os

from PyQt6 import QtCore, QtGui, QtWidgets

from app.configuration import configuration
from app.utils import vision_manager as vm

logger = logging.getLogger("Vision")


def build_vision_page(ui, create_scroll_page, create_glass_card, font_input):
    """Create the page widgets on ``ui`` and wire them. Returns the page widget."""
    tr = ui.translations.get
    page, layout = create_scroll_page()
    page.setObjectName("vision_tab")

    # ---------------- card 1: switch ----------------
    card, l = create_glass_card(tr("vision_title", "Vision (image understanding)"))
    intro = QtWidgets.QLabel(tr(
        "vision_intro",
        "A small separate vision model describes images (chat attachments, Discord images) so that every chat model - "
        "including text-only and local ones - can work with pictures. It runs in its own process on the GPU chosen under "
        "'AI Services' and is stopped automatically when idle."))
    intro.setWordWrap(True)
    intro.setStyleSheet("color: rgba(232,222,240,0.78); border: none; background: transparent;")
    l.addWidget(intro)

    ui.checkBox_vision_enabled = QtWidgets.QCheckBox(tr("vision_enable", "Enable vision plugin"))
    ui.checkBox_vision_enabled.setFont(font_input)
    l.addWidget(ui.checkBox_vision_enabled)

    form = QtWidgets.QFormLayout()
    form.setHorizontalSpacing(22)
    ui.comboBox_vision_mode = QtWidgets.QComboBox()
    ui.comboBox_vision_mode.setFont(font_input)
    ui.comboBox_vision_mode.setFixedHeight(40)
    ui.comboBox_vision_mode.addItem(tr("vision_mode_fallback", "Only if the chat model cannot see images (default)"), "fallback")
    ui.comboBox_vision_mode.addItem(tr("vision_mode_always", "Always (describe every image as text)"), "always")
    form.addRow(tr("vision_mode_label", "Use plugin"), ui.comboBox_vision_mode)
    ui.comboBox_vision_language = QtWidgets.QComboBox()
    ui.comboBox_vision_language.setFont(font_input)
    ui.comboBox_vision_language.setFixedHeight(40)
    ui.comboBox_vision_language.addItem(tr("vision_language_auto", "Same as app language (default)"), "auto")
    ui.comboBox_vision_language.addItem("Deutsch", "de")
    ui.comboBox_vision_language.addItem("English", "en")
    ui.comboBox_vision_language.addItem("Русский", "ru")
    form.addRow(tr("vision_language_label", "Description language"), ui.comboBox_vision_language)
    ui.spinBox_vision_idle = QtWidgets.QSpinBox()
    ui.spinBox_vision_idle.setRange(0, 240)
    ui.spinBox_vision_idle.setSuffix(" min")
    ui.spinBox_vision_idle.setFixedHeight(40)
    ui.spinBox_vision_idle.setToolTip(tr("vision_idle_tip", "Stop the vision model after this many idle minutes to free GPU memory. 0 = keep running."))
    form.addRow(tr("vision_idle_label", "Auto-stop when idle"), ui.spinBox_vision_idle)
    ui.comboBox_vision_image_px = QtWidgets.QComboBox()
    ui.comboBox_vision_image_px.setFixedHeight(40)
    for px in (512, 768, 1024, 1536):
        ui.comboBox_vision_image_px.addItem(f"{px} px", px)
    ui.comboBox_vision_image_px.setToolTip(tr("vision_px_tip", "Longest image side. Smaller = faster and less memory."))
    form.addRow(tr("vision_px_label", "Image size sent to the model"), ui.comboBox_vision_image_px)
    l.addLayout(form)
    layout.addWidget(card)

    # ---------------- where does it run: this PC or another PC (Yume LLM Server) ----------------
    from app.gui.vision_remote import build_vision_remote_card
    from app.gui.server_installer import build_installer_row
    layout.addWidget(build_vision_remote_card(ui, create_glass_card, font_input))
    layout.addWidget(build_installer_row(ui))

    # ---------------- card 2: model ----------------
    card2, l2 = create_glass_card(tr("vision_model_title", "Vision model"))
    ui.comboBox_vision_model = QtWidgets.QComboBox()
    ui.comboBox_vision_model.setFont(font_input)
    ui.comboBox_vision_model.setFixedHeight(40)
    l2.addWidget(ui.comboBox_vision_model)
    ui.label_vision_model_desc = QtWidgets.QLabel("")
    ui.label_vision_model_desc.setWordWrap(True)
    ui.label_vision_model_desc.setMinimumWidth(0)
    ui.label_vision_model_desc.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
    ui.label_vision_model_desc.setOpenExternalLinks(True)
    ui.label_vision_model_desc.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextBrowserInteraction)
    ui.label_vision_model_desc.setStyleSheet("color: rgba(232,222,240,0.78); border: none; background: transparent;")
    l2.addWidget(ui.label_vision_model_desc)

    row = QtWidgets.QHBoxLayout()
    ui.pushButton_vision_download = QtWidgets.QPushButton(tr("vision_download", "Download && install"))
    ui.pushButton_vision_download.setMinimumHeight(40)
    ui.pushButton_vision_delete = QtWidgets.QPushButton(tr("vision_delete", "Remove files"))
    ui.pushButton_vision_delete.setMinimumHeight(40)
    row.addWidget(ui.pushButton_vision_download)
    row.addWidget(ui.pushButton_vision_delete)
    l2.addLayout(row)
    ui.progressBar_vision = QtWidgets.QProgressBar()
    ui.progressBar_vision.setRange(0, 100)
    ui.progressBar_vision.setTextVisible(False)          # the percentage is part of the status line below (the bar text sat on the left edge)
    ui.progressBar_vision.setFixedHeight(8)
    ui.progressBar_vision.setStyleSheet(
        "QProgressBar { background: rgba(0,0,0,0.35); border: none; border-radius: 4px; } "
        "QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #FF8FC7, stop:1 #B69CFF); border-radius: 4px; }")
    ui.progressBar_vision.setVisible(False)
    l2.addWidget(ui.progressBar_vision)
    ui.label_vision_status = QtWidgets.QLabel("")
    ui.label_vision_status.setWordWrap(True)
    ui.label_vision_status.setMinimumWidth(0)
    ui.label_vision_status.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
    ui.label_vision_status.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    ui.label_vision_status.setStyleSheet("color: #d3a8ff; border: none; background: transparent;")
    l2.addWidget(ui.label_vision_status)

    ui.widget_vision_custom = QtWidgets.QWidget()
    cl = QtWidgets.QFormLayout(ui.widget_vision_custom)
    ui.lineEdit_vision_custom_model = QtWidgets.QLineEdit()
    ui.lineEdit_vision_custom_model.setReadOnly(True)
    ui.pushButton_vision_pick_model = QtWidgets.QPushButton(tr("vision_pick", "Choose..."))
    ui.lineEdit_vision_custom_mmproj = QtWidgets.QLineEdit()
    ui.lineEdit_vision_custom_mmproj.setReadOnly(True)
    ui.pushButton_vision_pick_mmproj = QtWidgets.QPushButton(tr("vision_pick", "Choose..."))
    r1, r2 = QtWidgets.QHBoxLayout(), QtWidgets.QHBoxLayout()
    r1.addWidget(ui.lineEdit_vision_custom_model, 1)
    r1.addWidget(ui.pushButton_vision_pick_model)
    r2.addWidget(ui.lineEdit_vision_custom_mmproj, 1)
    r2.addWidget(ui.pushButton_vision_pick_mmproj)
    cl.addRow(tr("vision_custom_model", "Model (.gguf)"), r1)
    cl.addRow(tr("vision_custom_mmproj", "Projector (mmproj .gguf)"), r2)
    l2.addWidget(ui.widget_vision_custom)
    layout.addWidget(card2)

    # ---------------- card 3: hardware, prompt, test ----------------
    card3, l3 = create_glass_card(tr("vision_hw_title", "Hardware, prompt & test"))
    ui.label_vision_hw = QtWidgets.QLabel("")
    ui.label_vision_hw.setWordWrap(True)
    ui.label_vision_hw.setStyleSheet("color: rgba(232,222,240,0.78); border: none; background: transparent;")
    l3.addWidget(ui.label_vision_hw)
    ui.pushButton_vision_open_ai_services = QtWidgets.QPushButton(tr("vision_open_ai_services", "Choose device / GPU (AI Services)"))
    ui.pushButton_vision_open_ai_services.setMinimumHeight(38)
    l3.addWidget(ui.pushButton_vision_open_ai_services)

    l3.addWidget(QtWidgets.QLabel(tr("vision_prompt_label", "Instruction for the vision model")))
    ui.plainTextEdit_vision_prompt = QtWidgets.QPlainTextEdit()
    ui.plainTextEdit_vision_prompt.setFixedHeight(100)
    ui.pushButton_vision_prompt_reset = QtWidgets.QPushButton(tr("vision_prompt_reset", "Restore default instruction"))
    l3.addWidget(ui.plainTextEdit_vision_prompt)
    l3.addWidget(ui.pushButton_vision_prompt_reset)

    trow = QtWidgets.QHBoxLayout()
    ui.pushButton_vision_test = QtWidgets.QPushButton(tr("vision_test", "Test with an image..."))
    ui.pushButton_vision_test.setMinimumHeight(40)
    ui.pushButton_vision_server = QtWidgets.QPushButton(tr("vision_server_stop", "Stop vision model"))
    ui.pushButton_vision_server.setMinimumHeight(40)
    trow.addWidget(ui.pushButton_vision_test)
    trow.addWidget(ui.pushButton_vision_server)
    l3.addLayout(trow)
    ui.plainTextEdit_vision_result = QtWidgets.QPlainTextEdit()
    ui.plainTextEdit_vision_result.setReadOnly(True)
    ui.plainTextEdit_vision_result.setFixedHeight(130)
    ui.plainTextEdit_vision_result.setPlaceholderText(tr("vision_result_hint", "The description of the test image appears here."))
    l3.addWidget(ui.plainTextEdit_vision_result)
    layout.addWidget(card3)
    layout.addStretch()

    ui.vision_controller = VisionController(ui)
    return page


class VisionController(QtCore.QObject):
    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.tr = ui.translations.get
        self.settings = configuration.ConfigurationSettings()
        self.worker = None
        self.test_worker = None
        self._loading = True
        self._fill_models()
        self._load_values()
        self._connect()
        self._loading = False
        self.refresh()

    # -- helpers --------------------------------------------------------------
    def _status(self, text: str):
        """Show a status line; very long texts (e.g. HTTP errors) are shortened so the
        page layout never changes, the full text stays available as tooltip."""
        label = self.ui.label_vision_status
        shown = text if len(text) <= 260 else text[:257] + "..."
        label.setText(shown)
        label.setToolTip(text if len(text) > 260 else "")

    def _friendly_error(self, message: str) -> str:
        low = message.lower()
        if "failed to resolve" in low or "nameresolution" in low or "name or service not known" in low:
            host = "the download server"
            for part in message.replace("'", " ").replace('"', " ").split():
                if part.count(".") >= 2 and part.startswith(("us.", "cdn", "huggingface", "cas-")) or part.endswith("hf.co"):
                    host = part.strip(",:()")
                    break
            return self.tr(
                "vision_err_dns",
                "Cannot reach {host}: the name could not be resolved. A DNS filter / firewall / VPN is probably blocking "
                "Hugging Face's download servers (*.hf.co). Allow it there, or download the files manually (links above).",
            ).format(host=host)
        if "timed out" in low or "connection" in low:
            return self.tr("vision_err_network", "Network error while downloading. Check your connection and try again.")
        return message

    def _set(self, key, value):
        if not self._loading:
            self.settings.update_main_setting(key, value)

    def _get(self, key, default=None):
        return vm.cfg(key, default)

    def _current_entry(self):
        return vm.entry_by_id(self.ui.comboBox_vision_model.currentData() or "")

    def _fill_models(self):
        combo = self.ui.comboBox_vision_model
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(self.tr("vision_model_none", "- no model selected -"), "")
        for entry in vm.CATALOG:
            mark = "  [installiert]" if vm.is_installed(entry) else f"  ({entry['size_gb']} GB)"
            combo.addItem(entry["name"] + mark, entry["id"])
        combo.addItem(self.tr("vision_model_custom", "Own model (choose files)..."), vm.CUSTOM_ID)
        combo.blockSignals(False)

    def _load_values(self):
        u = self.ui
        u.checkBox_vision_enabled.setChecked(bool(self._get("vision_enabled", False)))
        u.comboBox_vision_mode.setCurrentIndex(max(0, u.comboBox_vision_mode.findData(self._get("vision_mode", "fallback"))))
        u.comboBox_vision_language.setCurrentIndex(max(0, u.comboBox_vision_language.findData(self._get("vision_language", "auto"))))
        u.spinBox_vision_idle.setValue(int(self._get("vision_idle_minutes", 10) or 0))
        u.comboBox_vision_image_px.setCurrentIndex(max(0, u.comboBox_vision_image_px.findData(int(self._get("vision_max_image_px", 1024) or 1024))))
        u.comboBox_vision_model.setCurrentIndex(max(0, u.comboBox_vision_model.findData(self._get("vision_model_id", ""))))
        u.lineEdit_vision_custom_model.setText(str(self._get("vision_custom_model", "") or ""))
        u.lineEdit_vision_custom_mmproj.setText(str(self._get("vision_custom_mmproj", "") or ""))
        saved_prompt = str(self._get("vision_prompt", "") or "")
        u.plainTextEdit_vision_prompt.setPlainText(
            saved_prompt if saved_prompt and not vm.is_default_prompt(saved_prompt) else vm.default_prompt())

    def _connect(self):
        u = self.ui
        u.checkBox_vision_enabled.toggled.connect(lambda v: (self._set("vision_enabled", bool(v)), self.refresh()))
        u.comboBox_vision_mode.currentIndexChanged.connect(lambda _: self._set("vision_mode", u.comboBox_vision_mode.currentData()))
        u.comboBox_vision_language.currentIndexChanged.connect(lambda _: self._set("vision_language", u.comboBox_vision_language.currentData()))
        u.spinBox_vision_idle.valueChanged.connect(lambda v: self._set("vision_idle_minutes", int(v)))
        u.comboBox_vision_image_px.currentIndexChanged.connect(lambda _: self._set("vision_max_image_px", u.comboBox_vision_image_px.currentData()))
        u.comboBox_vision_model.currentIndexChanged.connect(self._on_model_changed)
        u.pushButton_vision_download.clicked.connect(self._on_download_clicked)
        u.pushButton_vision_delete.clicked.connect(self._on_delete)
        u.pushButton_vision_pick_model.clicked.connect(lambda: self._pick("vision_custom_model", u.lineEdit_vision_custom_model))
        u.pushButton_vision_pick_mmproj.clicked.connect(lambda: self._pick("vision_custom_mmproj", u.lineEdit_vision_custom_mmproj))
        u.plainTextEdit_vision_prompt.textChanged.connect(self._on_prompt_changed)
        u.pushButton_vision_prompt_reset.clicked.connect(lambda: u.plainTextEdit_vision_prompt.setPlainText(vm.default_prompt()))
        u.comboBox_vision_language.currentIndexChanged.connect(self._refresh_default_prompt)
        u.pushButton_vision_open_ai_services.clicked.connect(self._open_ai_services)
        u.pushButton_vision_test.clicked.connect(self._on_test)
        u.pushButton_vision_server.clicked.connect(self._on_server_toggle)

    # -- state ------------------------------------------------------------------
    def refresh(self):
        u = self.ui
        entry = self._current_entry()
        custom = u.comboBox_vision_model.currentData() == vm.CUSTOM_ID
        u.widget_vision_custom.setVisible(custom)
        busy = self.worker is not None and self.worker.isRunning()
        if entry:
            installed = vm.is_installed(entry)
            u.label_vision_model_desc.setText(
                f"{entry['desc']}<br><span style='color:#888'>~{entry['size_gb']} GB, "
                f"{self.tr('vision_min_vram', 'recommended from')} {entry['min_vram_gb']} GB VRAM</span><br>"
                f"<span style='color:#888'>{self.tr('vision_manual', 'Manual download (put both files into the folder assets/vision_models/' )}"
                f"{entry['id']}/):</span> " +
                " &nbsp;".join(f"<a href='{vm.HF}/{entry['repo']}/resolve/main/{name}'>{name}</a>" for name in entry["files"]))
            u.pushButton_vision_download.setVisible(True)
            u.pushButton_vision_download.setEnabled(not busy and not installed)
            u.pushButton_vision_download.setText(self.tr("vision_installed", "Installed") if installed else
                                                 self.tr("vision_download", "Download && install"))
            u.pushButton_vision_delete.setVisible(installed)
        else:
            u.label_vision_model_desc.setText(self.tr("vision_custom_note", "Choose a vision GGUF and its matching mmproj file.") if custom else "")
            u.pushButton_vision_download.setVisible(False)
            u.pushButton_vision_delete.setVisible(False)
        if busy:
            u.pushButton_vision_download.setEnabled(True)
            u.pushButton_vision_download.setText(self.tr("vision_cancel", "Cancel download"))
        if not busy:
            ready = vm.is_ready()
            if not u.checkBox_vision_enabled.isChecked():
                msg = self.tr("vision_state_off", "Vision plugin is off.")
            elif ready:
                msg = self.tr("vision_state_ready", "Ready. The model is loaded on first use.")
            else:
                msg = self.tr("vision_state_nomodel", "Enabled, but no installed model is selected.")
            self._status(msg)
        u.pushButton_vision_test.setEnabled(vm.is_ready())
        u.pushButton_vision_server.setText(self.tr("vision_server_stop", "Stop vision model") if vm.server.is_running()
                                           else self.tr("vision_server_start", "Load vision model now"))
        u.pushButton_vision_server.setEnabled(vm.is_ready() or vm.server.is_running())
        u.label_vision_hw.setText(self._hardware_text())

    def _hardware_text(self) -> str:
        device = str(self._get("vision_device", "cuda") or "cuda").lower()
        if device == "cpu":
            return self.tr("vision_hw_cpu", "Runs on the CPU (slower).")
        gpu = int(self._get("vision_gpu_index", 0) or 0)
        name = f"GPU {gpu}"
        try:
            import torch
            if torch.cuda.is_available():
                name = f"GPU {gpu}: {torch.cuda.get_device_name(min(gpu, torch.cuda.device_count() - 1))}"
        except Exception:
            pass
        return self.tr("vision_hw_gpu", "Runs on: {name}").format(name=name)

    def _open_ai_services(self):
        self.ui.select_option_tab(7)  # AI Services

    # -- actions ----------------------------------------------------------------
    def _on_prompt_changed(self):
        text = self.ui.plainTextEdit_vision_prompt.toPlainText().strip()
        # Store only user-written instructions; the default follows the answer language.
        self._set("vision_prompt", "" if (not text or vm.is_default_prompt(text)) else text)

    def _refresh_default_prompt(self, _index=None):
        """After a language change: show the matching default unless the user wrote their own."""
        if self._loading:
            return
        text = self.ui.plainTextEdit_vision_prompt.toPlainText().strip()
        if not text or vm.is_default_prompt(text):
            self.ui.plainTextEdit_vision_prompt.setPlainText(vm.default_prompt())

    def _on_model_changed(self, _index):
        model_id = self.ui.comboBox_vision_model.currentData() or ""
        self._set("vision_model_id", model_id)
        vm.server.stop()
        self.refresh()

    def _pick(self, key, line_edit):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self.ui.vision_tab, "GGUF", os.getcwd(), "GGUF (*.gguf)")
        if path:
            line_edit.setText(path)
            self._set(key, path)
            vm.server.stop()
            self.refresh()

    def _on_download_clicked(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            return
        entry = self._current_entry()
        if not entry or vm.is_installed(entry):
            return
        u = self.ui
        self.worker = vm.VisionDownloadWorker(entry)
        self.worker.progress.connect(lambda p, t: (u.progressBar_vision.setValue(p), self._status(f"{p} %  -  {t}")))
        self.worker.finished_ok.connect(self._on_download_done)
        self.worker.failed.connect(self._on_download_failed)
        self.worker.cancelled.connect(self._on_download_cancelled)
        u.progressBar_vision.setValue(0)
        u.progressBar_vision.setVisible(True)
        self.worker.start()
        self.refresh()

    def _download_finished_ui(self):
        self.ui.progressBar_vision.setVisible(False)
        self.worker = None
        self._fill_models_keep_selection()

    def _fill_models_keep_selection(self):
        current = self.ui.comboBox_vision_model.currentData()
        self._loading = True
        self._fill_models()
        self.ui.comboBox_vision_model.setCurrentIndex(max(0, self.ui.comboBox_vision_model.findData(current)))
        self._loading = False

    def _on_download_done(self, _folder):
        self._download_finished_ui()
        if not self.ui.checkBox_vision_enabled.isChecked():
            self.ui.checkBox_vision_enabled.setChecked(True)
        self.refresh()
        self._status(self.tr("vision_download_done", "Installed. The plugin is ready."))

    def _on_download_failed(self, message):
        self._download_finished_ui()
        self.refresh()
        logger.error("Vision model download failed: %s", message)
        self._status(self.tr("vision_download_failed", "Download failed: {error}").format(error=self._friendly_error(message)))
        self.ui.label_vision_status.setToolTip(message)

    def _on_download_cancelled(self):
        self._download_finished_ui()
        self.refresh()
        self._status(self.tr("vision_download_cancelled", "Download cancelled."))

    def _on_delete(self):
        entry = self._current_entry()
        if not entry:
            return
        answer = QtWidgets.QMessageBox.question(
            self.ui.vision_tab, entry["name"],
            self.tr("vision_delete_confirm", "Delete the downloaded files of this model?"))
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        vm.server.stop()
        vm.delete_entry(entry)
        self._fill_models_keep_selection()
        self.refresh()

    def _on_test(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.ui.vision_tab, "Image", os.getcwd(), "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        u = self.ui
        u.pushButton_vision_test.setEnabled(False)
        u.plainTextEdit_vision_result.setPlainText(self.tr("vision_test_running", "Loading the model and describing the image..."))
        self.test_worker = vm.DescribeWorker(path)
        self.test_worker.done.connect(self._on_test_done)
        self.test_worker.failed.connect(self._on_test_failed)
        self.test_worker.start()

    def _on_test_done(self, text):
        self.ui.plainTextEdit_vision_result.setPlainText(text)
        self.refresh()

    def _on_test_failed(self, message):
        self.ui.plainTextEdit_vision_result.setPlainText(self.tr("vision_test_failed", "Failed: {error}").format(error=message))
        self.refresh()

    def _on_server_toggle(self):
        if vm.server.is_running():
            vm.server.stop()
            self.refresh()
            return
        self.ui.pushButton_vision_server.setEnabled(False)
        self._status(self.tr("vision_loading", "Loading the vision model..."))
        class _Run(QtCore.QThread):
            ok = QtCore.pyqtSignal()
            bad = QtCore.pyqtSignal(str)

            def run(self_inner):
                try:
                    vm.server.ensure_running()
                    self_inner.ok.emit()
                except Exception as exc:
                    self_inner.bad.emit(str(exc))

        self._start_worker = _Run(self)
        self._start_worker.ok.connect(lambda: (self.refresh(), self._status(self.tr("vision_loaded", "Vision model loaded."))))
        self._start_worker.bad.connect(lambda m: (self.refresh(), self._status(m)))
        self._start_worker.start()
