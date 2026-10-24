import os as _os


def _boot_progress(percent, stage=""):
    """Reports the start-up progress to the launcher splash screen (only when launched by it)."""
    path = _os.environ.get("YUME_BOOT_FILE")
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"{int(percent)}|{stage}")
    except OSError:
        pass


_boot_progress(5, "start")

import os
import sys
import yaml
import torch
import ctypes
import psutil
import GPUtil
import asyncio
import threading
import logging
import requests
_boot_progress(20, "libraries")
from datetime import datetime
from qasync import QEventLoop, asyncSlot

from PyQt6.QtGui import QFontDatabase
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox

from app.configuration import configuration
from app.gui.icons import resources
from app.gui import interface_signals
from app.utils.ai_clients.local_server_manager import LocalServerManager
from app.gui.sowInterface import Ui_MainWindow

from app.gui.custom_widgets import SowConfirmDialog
_boot_progress(60, "interface")

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_file = os.path.join(LOG_DIR, f"sow_{timestamp}.log")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s [%(levelname)s] - %(name)s: %(message)s')

file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

logging.root = logger
logging.root.setLevel(logging.INFO)

logger.propagate = False

logger.info("========================================")
logger.info(f"Logging started. Output will be written to: {log_file}")
logger.info(f"All logs will be saved in 'logs' folder")
logger.info("========================================")

def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Unhandled exception captured:", exc_info=(exc_type, exc_value, exc_traceback))
    
    if QApplication.instance():
        try:
            QMessageBox.critical(
                None, 
                "Critical Error", 
                f"An unexpected error occurred:\n{exc_value}\n\nPlease check the logs for details."
            )
        except Exception:
            pass

sys.excepthook = global_exception_handler

from app.utils.discord_manager import DiscordBotManager
from app.utils.branding import load_branding, app_icon_path, resolve_branding_path, build_app_icon, taskbar_app_id, apply_taskbar_icon
from app.utils.aec_manager import probe_aec_installation, install_aec_dependency
from app.utils.backup_manager import BackupManager, BackupError

RESIZE_GRIP_SIZE = 8

class _AECInstallWorker(QtCore.QThread):
    result_ready = QtCore.pyqtSignal(bool, str)

    def run(self):
        try:
            ok, detail = install_aec_dependency()
        except Exception as exc:
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        self.result_ready.emit(bool(ok), str(detail))

class _EdgeResizeGrip(QtWidgets.QWidget):
    def __init__(self, window: QtWidgets.QMainWindow, edges: QtCore.Qt.Edge,
                 cursor: QtCore.Qt.CursorShape, parent=None):
        super().__init__(parent)
        self._window = window
        self._edges = edges
        self.setCursor(cursor)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

    def mousePressEvent(self, event):
        if (event.button() == QtCore.Qt.MouseButton.LeftButton
                and not self._window.isMaximized()
                and not self._window.isFullScreen()):
            handle = self._window.windowHandle()
            if handle is not None and handle.startSystemResize(self._edges):
                event.accept()
                return
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    """
    Main application window for 'Soul of Waifu'.
    """
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setAcceptDrops(True)

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        if self.ui.comboBox_program_language.count() < 3:
            self.ui.comboBox_program_language.addItem("German")

        self.discord_manager = DiscordBotManager(self)

        self.translations = {}

        self.draggable = False
        self.offset = None

        self.ui.minimize_btn.clicked.connect(self.showMinimized)
        self.ui.maximize_btn.clicked.connect(self.toggle_maximize)
        self.ui.close_app_btn.clicked.connect(self.close)

        self.configuration = configuration.ConfigurationSettings()
        selected_language = self.configuration.get_main_setting("program_language")
    
        match selected_language:
            case 0:
                self.load_translation("en")
                self.apply_translations()
            case 1:
                self.load_translation("ru")
                self.apply_translations()
            case 2:
                self.load_translation("de")
                self.apply_translations()
            case _:
                self.load_translation("en")
                self.apply_translations()

        self.interface_signals = interface_signals.InterfaceSignals(self.ui, self)
        self.local_server_manager = LocalServerManager(self.ui)

        self.create_size_grips()
        QtCore.QTimer.singleShot(0, self.update_size_grip_positions)

        self.interface_signals.load_background_images_to_comboBox()
        self.interface_signals.load_ambient_sound_to_comboBox()
        self.interface_signals.load_combobox()
        self.setup_interface_signals()
        self.interface_signals.load_audio_devices()
        self.interface_signals.update_api_token()
        self.check_pc_specs()

        self.interface_signals.initialize_api_token_line_edit()
        self.interface_signals.initialize_lineEdit_customArgs()
        self.interface_signals.initialize_lineEdit_mcp_url()
        self.interface_signals.initialize_extended_settings()
        self._aec_install_worker = None
        self.ui.pushButton_aec_check_install.clicked.connect(self._on_aec_check_install_clicked)
        QtCore.QTimer.singleShot(1400, self._check_aec_on_startup)
        self.interface_signals.initialize_gpu_layers_horizontalSlider()
        self.interface_signals.initialize_context_size_horizontalSlider()
        self.interface_signals.initialize_temperature_horizontalSlider()
        self.interface_signals.initialize_top_p_horizontalSlider()
        self.interface_signals.initialize_max_tokens_horizontalSlider()
        self.interface_signals.initialize_interval_summary()
        self.interface_signals.initialize_freq_penalty_horizontalSlider()
        self.interface_signals.initialize_pres_penalty_horizontalSlider()
        self.interface_signals.initialize_min_p_horizontalSlider()
        self.interface_signals.initialize_dyn_temp_min_horizontalSlider()
        self.interface_signals.initialize_dyn_temp_max_horizontalSlider()
        self.interface_signals.initialize_xtc_prob_horizontalSlider()
        self.interface_signals.initialize_xtc_threshold_horizontalSlider()
        self.interface_signals.initialize_dry_multiplier_horizontalSlider()
        self.interface_signals.initialize_dry_base_horizontalSlider()
        self.interface_signals.initialize_dry_allowed_length_horizontalSlider()
        self.interface_signals.initialize_batch_size_horizontalSlider()
        self.interface_signals.initialize_cpu_threads_horizontalSlider()
        self.interface_signals.initialize_cpu_moe_layers_horizontalSlider()
        self.interface_signals.populate_llm_presets_combobox()
        try:
            self.interface_signals._add_llm_reset_button()
        except Exception:
            logging.getLogger("SoW").exception("LLM reset button could not be created")

        self.drop_overlay = QtWidgets.QLabel(self)
        self.drop_overlay.setText(self.translations.get("drag_and_drop_overlay", "Drag and drop a .png or .json card directly here\nto import it into Soul of Waifu"))
        self.drop_overlay.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.drop_overlay.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 200);
                color: white;
                font-size: 24px;
                font-family: 'Inter Tight Medium';
            }
        """)
        self.drop_overlay.hide()

    def _set_aec_status(self, available: bool, detail: str):
        try:
            if available:
                text = self.translations.get("aec_status_ready", "WebRTC AEC3 bereit. Vollduplex-Echoentfernung ist verfügbar.")
                self.ui.label_aec_status.setText(f"{text}\n{detail}")
                self.ui.label_aec_status.setStyleSheet("color: #6FCF97; font-size: 11px; background: transparent; border: none;")
                self.ui.spinBox_aec_stream_delay.setEnabled(True)
                self.ui.checkBox_aec_noise_suppression.setEnabled(True)
                self.ui.pushButton_aec_check_install.setText(self.translations.get("aec_recheck_button", "AEC3 erneut prüfen"))
            else:
                text = self.translations.get("aec_status_missing", "WebRTC AEC3 fehlt oder kann nicht initialisiert werden. Im AEC-Modus greift bis zur Reparatur Halbduplex.")
                self.ui.label_aec_status.setText(f"{text}\n{detail}")
                self.ui.label_aec_status.setStyleSheet("color: #F6C177; font-size: 11px; background: transparent; border: none;")
                self.ui.spinBox_aec_stream_delay.setEnabled(False)
                self.ui.checkBox_aec_noise_suppression.setEnabled(False)
                self.ui.pushButton_aec_check_install.setText(self.translations.get("aec_install_button", "WebRTC AEC3 prüfen / installieren"))
        except Exception:
            logger.debug("Could not refresh AEC status UI", exc_info=True)

    def _check_aec_on_startup(self):
        """Check AEC3 on every launch; offer installation once if missing."""
        try:
            available, detail = probe_aec_installation()
            self._set_aec_status(available, detail)
            if available:
                logger.info("AEC startup check passed: %s", detail)
                return
            logger.warning("AEC startup check failed: %s", detail)
            try:
                dismissed = bool(self.configuration.get_main_setting("aec_install_prompt_dismissed"))
                dismissed_version = int(self.configuration.get_main_setting("aec_install_prompt_version") or 0)
            except (TypeError, ValueError):
                dismissed, dismissed_version = False, 0
            # Earlier 2.5.3 packages could store only a generic dismissed flag.
            # Re-prompt once for this repair release so users are not stuck with
            # the missing AEC installer; future explicit dismissal is remembered.
            if dismissed and dismissed_version >= 253:
                return
            answer = QMessageBox.question(
                self,
                self.translations.get("aec_install_title", "WebRTC AEC3 fehlt"),
                self.translations.get(
                    "aec_install_prompt",
                    "Die WebRTC-AEC3-Installation fehlt oder funktioniert nicht. Soll sie jetzt in der Python-Umgebung installiert/repariert werden, die Soul of Waifu tatsächlich nutzt? Dafür wird Internetzugriff benötigt."
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._begin_aec_install()
            else:
                self.configuration.update_main_setting("aec_install_prompt_dismissed", True)
                self.configuration.update_main_setting("aec_install_prompt_version", 253)
        except Exception:
            logger.exception("AEC startup dependency check failed")

    def _on_aec_check_install_clicked(self):
        if self._aec_install_worker is not None and self._aec_install_worker.isRunning():
            return
        available, detail = probe_aec_installation()
        self._set_aec_status(available, detail)
        if available:
            QMessageBox.information(
                self,
                self.translations.get("aec_install_title", "WebRTC AEC3"),
                self.translations.get("aec_status_ready", "WebRTC AEC3 bereit.") + "\n\n" + detail,
            )
            return
        self._begin_aec_install()

    def _begin_aec_install(self):
        if self._aec_install_worker is not None and self._aec_install_worker.isRunning():
            return
        self.configuration.update_main_setting("aec_install_prompt_dismissed", False)
        self.ui.pushButton_aec_check_install.setEnabled(False)
        self.ui.label_aec_status.setText(self.translations.get("aec_status_installing", "WebRTC AEC3 wird installiert – bitte warten …"))
        self._aec_install_worker = _AECInstallWorker(self)
        self._aec_install_worker.result_ready.connect(self._on_aec_install_result)
        self._aec_install_worker.start()

    def _on_aec_install_result(self, available: bool, detail: str):
        self._set_aec_status(available, detail)
        self.ui.pushButton_aec_check_install.setEnabled(True)
        if available:
            self.configuration.update_main_setting("aec_install_prompt_dismissed", False)
            self.configuration.update_main_setting("aec_install_prompt_version", 253)
            QMessageBox.information(
                self,
                self.translations.get("aec_install_title", "WebRTC AEC3"),
                self.translations.get("aec_install_success", "WebRTC AEC3 wurde installiert und die Initialisierung war erfolgreich.") + "\n\n" + detail + "\n\n" + self.translations.get("aec_install_restart_note", "Bitte den Sprachmodus neu starten; bei Problemen Soul of Waifu neu starten."),
            )
        else:
            QMessageBox.warning(
                self,
                self.translations.get("aec_install_title", "WebRTC AEC3"),
                self.translations.get("aec_install_failure", "AEC3 konnte nicht installiert oder initialisiert werden. Die Anwendung verwendet weiterhin Halbduplex.") + "\n\n" + detail,
            )

    async def startup_sequence(self):
        await self.interface_signals.set_main_tab()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith(('.png', '.json')):
                    self.drop_overlay.resize(self.size())
                    self.drop_overlay.show()
                    self.drop_overlay.raise_()
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.drop_overlay.hide()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.drop_overlay.hide()
        if not event.mimeData().hasUrls():
            return
            
        for url in event.mimeData().urls():
            if url.isLocalFile() and url.toLocalFile().lower().endswith(('.png', '.json')):
                file_path = url.toLocalFile()
                
                if hasattr(self, 'interface_signals'):
                    self.interface_signals.populate_editor_character_list()
                    self.interface_signals.prepare_new_character_editor()
                    self.interface_signals.import_character_card(file_path)
                    self.ui.stackedWidget.setCurrentWidget(self.ui.create_character_page)
                event.acceptProposedAction()
                return

    def load_translation(self, language):
        """
        Loads translation strings from a YAML file based on the program language.
        """
        file_path = f"app/translations/{language}.yaml"
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as file:
                self.translations = yaml.safe_load(file) or {}
        else:
            self.translations = {}
    
    def apply_translations(self):
        """
        Applies loaded translations to static UI elements.
        """
        self.setWindowTitle(self.translations.get("program_title", "Soul of Waifu"))
        branding = load_branding()
        custom_name = str(branding.get("app_name", "")).strip()
        if custom_name:
            self.setWindowTitle(custom_name)
        self.setWindowIcon(build_app_icon())
        custom_logo = resolve_branding_path("logo_path")
        if custom_logo and hasattr(self.ui, "label_logotype"):
            pixmap = QtGui.QPixmap(str(custom_logo))
            if not pixmap.isNull():
                self.ui.label_logotype.setPixmap(pixmap)
        if self.ui.comboBox_program_language.count() < 3:
            self.ui.comboBox_program_language.addItem("German")
        self.ui.comboBox_program_language.setItemText(2, self.translations.get("program_language_item_de", "German"))
        
        # Left Menu
        self.ui.pushButton_main.setText(self.translations.get("main_button", " Main"))
        self.ui.pushButton_characters_gateway.setText(self.translations.get("characters_gateway_button", " Characters Gateway"))
        self.ui.pushButton_models_hub.setText(self.translations.get("models_hub_button", " Models Hub"))
        self.ui.pushButton_rp_editors.setText(self.translations.get("rp_editors_button", " RP Editors"))
        self.ui.pushButton_soul_stage.setText(self.translations.get("soul_stage_button", " Soul Stage"))
        self.ui.pushButton_options.setText(self.translations.get("options_button", " Options"))
        _brand_name = custom_name or "Soul of Waifu"
        self.ui.version_label.setText(self.translations.get("version_label", f"{_brand_name} v3.0.0 BETA"))
        if custom_name and "Soul of Waifu" in self.ui.version_label.text():
            self.ui.version_label.setText(self.ui.version_label.text().replace("Soul of Waifu", custom_name))
        # Hide sidebar link buttons whose link was removed in the branding file.
        from app.utils.branding import get_url
        for _btn, _key in (("pushButton_youtube", "youtube_url"), ("pushButton_discord", "discord_url"),
                           ("pushButton_github", "github_url")):
            if hasattr(self.ui, _btn):
                getattr(self.ui, _btn).setVisible(bool(get_url(_key, branding)))
        sidebar_logo = resolve_branding_path("sidebar_logo_path")
        if sidebar_logo and hasattr(self.ui, "label_logotype"):
            _px = QtGui.QPixmap(str(sidebar_logo))
            if not _px.isNull():
                self.ui.label_logotype.setPixmap(_px)
        
        # Main Tab Without Characters
        self.ui.main_no_characters_advice_label.setText(self.translations.get("no_characters_advice", "You haven\'t added any characters. Click on the button and create it"))
        self.ui.pushButton_create_character_2.setText(self.translations.get("create_character_button_2", " Create Character"))
        self.ui.main_no_characters_description_label.setText(self.translations.get("no_characters_description", "Before you begin a chat with a character, take a moment to customize the program to suit your preferences. \n"
"Once you\'re ready, create your unique character and start the conversation!"))
        
        # Main Tab With Characters
        self.ui.welcome_label_2.setText(self.translations.get("welcome_label", "Welcome to Soul of Waifu, User"))
        self.ui.lineEdit_search_character_menu.setPlaceholderText(self.translations.get("search_placeholder", "Search"))
        
        # Character Creation
        self.ui.pushButton_import_character_card.setText(self.translations.get("import_character_card_button", " Import Character Card"))
        self.ui.pushButton_export_character_card.setText(self.translations.get("export_character_card_button", " Export Character Card"))
        self.ui.pushButton_clean_character_card.setText(self.translations.get("clean_character_card_button", " Clear All Fields"))
        self.ui.pushButton_preview_prompt.setText(self.translations.get("preview_prompt_button", "Preview Raw"))
        self.ui.character_image_building_label.setText(self.translations.get("character_image_building_label", "Character\'s Image"))
        self.ui.character_name_building_label.setText(self.translations.get("character_name_building_label", "Character\'s Name"))
        self.ui.lineEdit_character_name_building.setPlaceholderText(self.translations.get("placeholder_character_name", "The name of your character"))
        self.ui.character_description_building_label.setText(self.translations.get("character_description_building_label", "Character\'s Description"))
        self.ui.textEdit_character_description_building.setPlaceholderText(self.translations.get("placeholder_character_description", "Used to provide the character description and other essential information the AI should know. It should contain all important facts"))
        self.ui.character_personality_building_label.setText(self.translations.get("character_personality_building_label", "Character\'s Personality"))
        self.ui.textEdit_character_personality_building.setPlaceholderText(self.translations.get("placeholder_character_personality", "A summary of the character’s personality"))
        self.ui.character_scenario_building_label.setText(self.translations.get("scenario", "Scenario"))
        self.ui.textEdit_scenario.setPlaceholderText(self.translations.get("placeholder_scenario", "Conversation scenario"))
        self.ui.first_message_building_label.setText(self.translations.get("first_message_building_label", "First Message"))
        self.ui.textEdit_first_message_building.setPlaceholderText(self.translations.get("placeholder_first_message", "The First Message is crucial as it sets the tone, style, and manner in which the character will communicate"))
        self.ui.example_messages_building_label.setText(self.translations.get("example_messages_title", "Example Messages"))
        self.ui.textEdit_example_messages.setPlaceholderText(self.translations.get("placeholder_example_messages", "Describes how the character speaks. Before each example, you must insert the <START> macro"))
        self.ui.alternate_greetings_building_label.setText(self.translations.get("alternate_greetings_label", "Alternate Greetings"))
        self.ui.textEdit_alternate_greetings.setPlaceholderText(self.translations.get("placeholder_alternate_greetings", "You can include as many alternative greetings as you like. Before each alternate greeting, you must insert the <GREETING> macro"))
        self.ui.creator_notes_building_label.setText(self.translations.get("creator_notes_label", "Creator Notes"))
        self.ui.textEdit_creator_notes.setPlaceholderText(self.translations.get("placeholder_creator_notes", "Any additional notes about the character card"))
        self.ui.character_version_building_label.setText(self.translations.get("card_version_label", "Character Card Version"))
        self.ui.textEdit_character_version.setPlaceholderText(self.translations.get("placeholder_card_version", "The version of the character card"))
        self.ui.user_persona_building_label.setText(self.translations.get("user_persona_building_label", "User Persona"))
        self.ui.system_prompt_building_label.setText(self.translations.get("system_prompt_building_label", "System Prompt Preset"))
        self.ui.lorebook_building_label.setText(self.translations.get("lorebook_building_label", "Lorebook"))
        self.ui.pushButton_create_character_3.setText(self.translations.get("create_character_button_3", "Create Character"))
        self.ui.total_tokens_building_label.setText(self.translations.get("total_tokens_label", "Total Tokens: 0"))
        self.ui.item_general_info.setText(self.translations.get("character_creator_item_general_info", "General Information"))
        self.ui.item_personality.setText(self.translations.get("character_creator_item_personality", "Personality & Scenario"))
        self.ui.item_dialogues.setText(self.translations.get("character_creator_item_dialogues", "Dialogues"))
        self.ui.item_advanced.setText(self.translations.get("character_creator_item_advanced", "Advanced & Lore"))
        self.ui.item_variables.setText(self.translations.get("character_creator_title_custom_variable", "Variables & State"))
        self.ui.item_export.setText(self.translations.get("character_creator_item_export", "Export / Utils"))
        
        # Models Hub
        self.ui.lineEdit_search_model.setPlaceholderText(self.translations.get("search_placeholder", "Search"))
        self.ui.pushButton_models_hub_my_models.setText(self.translations.get("models_hub_my_models", " My models"))
        self.ui.pushButton_models_hub_popular.setText(self.translations.get("models_hub_popular", " Popular"))
        self.ui.pushButton_models_hub_recommendations.setText(self.translations.get("models_hub_recommendations", "Recommendations"))

        # Options
        self.ui.label_base_url.setText(self.translations.get("label_base_url", "Base URL"))
        self.ui.label_mistral_model.setText(self.translations.get("label_mistral_model", "Mistral Model"))
        self.ui.label_bg_color.setText(self.translations.get("model_background_1", "Color"))
        self.ui.label_bg_image.setText(self.translations.get("model_background_2", "Image"))
        self.ui.lineEdit_search_character.setPlaceholderText(self.translations.get("search_placeholder", "Search"))
        self.ui.conversation_method_token_title_label.setText(self.translations.get("api_label", "API"))
        self.ui.lineEdit_api_token_options.setPlaceholderText(self.translations.get("placeholder_api_value", "Write your API value here"))
        self.ui.lineEdit_mistral_model.setPlaceholderText(self.translations.get("placeholder_mistral_model_endpoint", "Enter the API endpoint of the mistral model here"))
        self.ui.checkBox_enable_sow_system.setText(self.translations.get("enable_sow_system_checkbox", "Enable Yume System"))
        self.ui.label_model_fps.setText(self.translations.get("choose_model_fps", "Model FPS"))
        self.ui.comboBox_model_fps.setItemText(0, self.translations.get("model_fps_30", "30 FPS"))
        self.ui.comboBox_model_fps.setItemText(1, self.translations.get("model_fps_60", "60 FPS"))
        self.ui.comboBox_model_fps.setItemText(2, self.translations.get("model_fps_120", "120 FPS"))
        self.ui.label_model_background.setText(self.translations.get("choose_model_background", "Model background"))
        self.ui.comboBox_model_background.setItemText(0, self.translations.get("model_background_1", "Color"))
        self.ui.comboBox_model_background.setItemText(1, self.translations.get("model_background_2", "Custom Image"))
        self.ui.checkBox_enable_ambient.setText(self.translations.get("enable_ambient_checkbox", "Ambient Sound"))
        self.ui.checkBox_enable_soul_memory.setText(self.translations.get("enable_soul_memory", "Soul Memory"))
        self.ui.checkBox_enable_summary.setText(self.translations.get("enable_summary_checkbox", "Auto-Summarization"))
        self.ui.label_summary_interval.setText(self.translations.get("settings_summary_interval", "Interval (messages):"))
        self.ui.conversation_method_options_label.setText(self.translations.get("conversation_method_label", "Conversation method"))
        self.ui.openrouter_models_options_label.setText(self.translations.get("openrouter_models_label", "Model"))
        self.ui.lineEdit_search_openrouter_models.setPlaceholderText(self.translations.get("search_placeholder", "Search"))
        self.ui.lineEdit_base_url_options.setPlaceholderText(self.translations.get("placeholder_base_url", "Write your custom endpoint url here (Optional)"))
        self.ui.comboBox_program_language.setItemText(0, self.translations.get("program_language_item_en", "English"))
        self.ui.comboBox_program_language.setItemText(1, self.translations.get("program_language_item_ru", "Russian"))
        self.ui.input_device_label.setText(self.translations.get("input_device_label", "Input device"))
        self.ui.output_device_label.setText(self.translations.get("output_device_label", "Output device"))
        self.ui.program_language_label.setText(self.translations.get("program_language_label", "App Language"))
        self.ui.choose_translator_label.setText(self.translations.get("choose_translator_label", "Translator"))
        self.ui.comboBox_translator.setItemText(0, self.translations.get("translator_item_none", "None"))
        self.ui.comboBox_translator.setItemText(1, self.translations.get("translator_item_google", "Google"))
        self.ui.comboBox_translator.setItemText(2, self.translations.get("translator_item_yandex", "Yandex"))
        self.ui.comboBox_tts_voicing_mode.setItemText(0, self.translations.get("tts_mode_voice_everything", "Voice Everything"))
        self.ui.comboBox_tts_voicing_mode.setItemText(1, self.translations.get("tts_mode_voice_quotes", "Voice Only Quotes"))
        self.ui.comboBox_tts_voicing_mode.setItemText(2, self.translations.get("tts_mode_ignore_asterisks", "Ignore Asterisks"))
        self.ui.comboBox_tts_voicing_mode.setItemText(3, self.translations.get("tts_mode_voice_outside_quotes", "Voice Outside Quotes"))
        self.ui.comboBox_tts_voicing_mode.setItemText(4, self.translations.get("tts_mode_custom_regex", "Custom Regex"))
        self.ui.comboBox_translator.setItemText(3, self.translations.get("translator_item_ai", "AI Translator (Current Model)"))
        self.ui.target_language_translator_label.setText(self.translations.get("target_language_label", "Target Language"))
        self.ui.comboBox_target_language_translator.setItemText(0, self.translations.get("target_language_item_ru", "Russian"))
        self.ui.checkBox_auto_translate_new_messages.setText(
            self.translations.get("checkbox_auto_translate_new_messages", "Automatically translate new messages")
        )
        self.ui.checkBox_auto_translate_new_messages.setToolTip(
            self.translations.get(
                "auto_translate_new_messages_tooltip",
                "When enabled, every new character message is translated automatically.\nWhen disabled, messages stay in their original language and you can translate\nany of them manually via the Translate action in the message menu."
            )
        )

        if hasattr(self.ui, "options_menu"):
            # Keep sidebar labels aligned with the settings stack's actual page order.
            option_tab_keys = [
                ("settings_system_ui", "System & UI"),
                ("settings_api_providers", "API & Providers"),
                ("settings_local_llm", "Local LLM"),
                ("settings_vision", "Vision AI"),
                ("settings_tool_calling_mcp", "Tool Calling & MCP"),
                ("settings_home_assistant", "Home Assistant"),
                ("settings_tools_plugins", "Tools & Plugins"),
                ("settings_ai_services", "AI Services"),
                ("settings_conversation_audio", "Conversation & Audio"),
                ("settings_sow_modules", "Yume Modules"),
                ("settings_android_connector", "Android Connector"),
                ("settings_appearance", "Appearance"),
                ("settings_backup_restore", "Backup & Restore"),
                ("settings_updates", "Updates"),
                ("settings_dashboard", "Dashboard"),
            ]
            group_fallbacks = dict(getattr(self.ui, "options_nav_group_keys", []))
            for row in range(self.ui.options_menu.count()):
                item = self.ui.options_menu.item(row)
                idx = item.data(QtCore.Qt.ItemDataRole.UserRole)
                group_key = item.data(QtCore.Qt.ItemDataRole.UserRole + 1)
                if idx is not None and 0 <= idx < len(option_tab_keys):
                    key, fallback = option_tab_keys[idx]
                    item.setText(self.translations.get(key, fallback))
                elif group_key:
                    item.setText(self.translations.get(group_key, group_fallbacks.get(group_key, "")).upper())
            if hasattr(self.ui, "settings_nav"):
                self.ui.settings_nav.retranslate(self.translations)
        
        # Chat
        self.ui.character_name_chat.setText(self.translations.get("character_name_chat", "Character name"))
        self.ui.textEdit_write_user_message.setPlaceholderText(self.translations.get("write_user_message_placeholder", "Write your message to character..."))
        
        # LLM Options
        self.ui.label_live2d_mode.setText(self.translations.get("live2d_mode_label", "Mode:"))
        self.ui.comboBox_live2d_mode.setItemText(0, self.translations.get("live2d_mode_with_gui", "With GUI"))
        self.ui.comboBox_live2d_mode.setItemText(1, self.translations.get("live2d_mode_without_gui", "Without GUI"))
        self.ui.checkBox_enable_nsfw.setText(self.translations.get("nsfw_checkbox", "NSFW"))
        self.ui.lineEdit_server.setText("http://localhost:48596/v1")

        # Tooltips
        self.ui.checkBox_enable_mlock.setToolTip(self.translations.get("mlock_tooltip", ""))
        self.ui.checkBox_enable_no_mmap.setToolTip(self.translations.get("no_mmap_tooltip", ""))
        self.ui.checkBox_reasoning_mode.setToolTip(self.translations.get("reasoning_mode_tooltip", ""))
        self.ui.checkBox_enable_flash_attention.setToolTip(self.translations.get("flashattention_tooltip", ""))
        self.ui.checkBox_enable_ambient.setToolTip(self.translations.get("ambient_sound_tooltip", "Enable Ambient Sound Module"))
        self.ui.checkBox_enable_soul_memory.setToolTip(self.translations.get("soul_memory_tooltip", "Enable Soul Memory Module"))
        self.ui.checkBox_enable_sow_system.setToolTip(self.translations.get("sow_system_tooltip", "Enable Yume System Module"))
        self.ui.chat_template_label.setToolTip(self.translations.get("chat_template_tooltip", ""))
        self.ui.lineEdit_stop_strings.setToolTip(self.translations.get("stop_strings_tooltip", ""))

    def _backup_manager(self):
        return BackupManager()

    def _init_updates_tab(self):
        from app.utils.update_checker import current_version, DEFAULT_REPO
        self._update_release_url = ""
        self._update_worker = None
        self.ui.label_update_current.setText(
            self.translations.get("updates_current_version", "Installed version: {version}").format(version=current_version())
        )
        repo = self.interface_signals.configuration_settings.get_main_setting("update_repo") or DEFAULT_REPO
        self.ui.lineEdit_update_repo.setText(repo)

    def on_update_repo_edited(self):
        from app.utils.update_checker import normalize_repo
        raw = self.ui.lineEdit_update_repo.text().strip()
        repo = normalize_repo(raw) if raw else ""
        if raw and not repo:
            self.ui.label_update_status.setText(self.translations.get(
                "updates_invalid_repo", "Invalid repository. Use the form owner/repository or a github.com URL."))
            return
        self.ui.lineEdit_update_repo.setText(repo)
        self.interface_signals.configuration_settings.update_main_setting("update_repo", repo)

    def on_check_updates_clicked(self):
        from app.utils.update_checker import UpdateCheckWorker, normalize_repo
        if self._update_worker is not None and self._update_worker.isRunning():
            return
        repo = normalize_repo(self.ui.lineEdit_update_repo.text())
        if not repo:
            self.ui.label_update_status.setText(self.translations.get(
                "updates_not_configured",
                "No GitHub repository configured yet. Enter it above (owner/repository) once the project is published."))
            return
        self.on_update_repo_edited()
        self.ui.pushButton_check_updates.setEnabled(False)
        self.ui.pushButton_open_release_page.setEnabled(False)
        self.ui.label_update_status.setText(self.translations.get("updates_checking", "Checking GitHub..."))
        self._update_worker = UpdateCheckWorker(repo, self)
        self._update_worker.finished_check.connect(self._on_update_check_finished)
        self._update_worker.start()

    def _on_update_check_finished(self, result: dict):
        self.ui.pushButton_check_updates.setEnabled(True)
        tr = self.translations
        if not result.get("ok"):
            errors = {
                "not_configured": tr.get("updates_not_configured", "No GitHub repository configured yet."),
                "repo_not_found": tr.get("updates_repo_not_found", "Repository not found (or private)."),
                "no_releases": tr.get("updates_no_releases", "The repository has no releases or tags yet."),
                "rate_limited": tr.get("updates_rate_limited", "GitHub rate limit reached. Try again later."),
                "network": tr.get("updates_network_error", "Could not reach GitHub. Check your internet connection."),
            }
            fallback = tr.get("updates_error", "Update check failed: {error}").format(error=result.get("error"))
            self.ui.label_update_status.setText(errors.get(result.get("error"), fallback))
            return
        self._update_release_url = result.get("url", "")
        self.ui.pushButton_open_release_page.setEnabled(bool(self._update_release_url))
        if result.get("newer"):
            text = tr.get("updates_available", "New version available: {remote} (installed: {local}).").format(
                remote=result["remote"], local=result["local"])
            if result.get("notes"):
                text += "\n\n" + result["notes"]
        else:
            text = tr.get("updates_up_to_date", "You are up to date (installed: {local}, latest: {remote}).").format(
                remote=result["remote"], local=result["local"])
        self.ui.label_update_status.setText(text)

    def on_open_release_page_clicked(self):
        url = getattr(self, "_update_release_url", "")
        if url.startswith("https://github.com/"):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def on_create_backup_clicked(self):
        """Export a backup as a Yume backup file (.yumepack) - the same format as the profile backup below on this page."""
        try:
            ctrl = self.ui.profile_backup_controller
            ctrl._set_default_path()
            destination, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                self.translations.get("backup_create_dialog_title", "Create Yume Backup"),
                self.ui.pbackup_path.text(),
                "Yume Backup (*.yumepack)",
            )
            if not destination:
                return
            if not destination.lower().endswith(".yumepack"):
                destination += ".yumepack"
            self.ui.pbackup_path.setText(destination)
            # "include assets" of this card = the asset groups of the profile backup (media, Live2D/VRM, voices, RVC models)
            include_assets = bool(self.ui.checkBox_backup_include_assets.isChecked())
            for key in ("media_assets", "live2d_assets", "tts_voices", "rvc_models"):
                entry = self.ui.pbackup_checks.get(key)
                if entry:
                    entry[0].setChecked(include_assets)
            ctrl.start_export()
            self.ui.label_backup_status.setText(self.translations.get("backup_started_status", "Backup is being created …"))
        except Exception as exc:
            logger.exception("Backup creation failed")
            QtWidgets.QMessageBox.critical(
                self,
                self.translations.get("backup_error_title", "Backup error"),
                f"{exc}",
            )

    def _restore_backup_from(self, source: str):
        manager = self._backup_manager()
        preview = manager.inspect_backup(source)
        source_version = preview.get("source_version", "unknown")
        count = preview.get("file_count", 0)
        answer = QtWidgets.QMessageBox.question(
            self,
            self.translations.get("backup_restore_confirm_title", "Confirm backup restore"),
            self.translations.get(
                "backup_restore_confirm_message",
                "Import backup from version {version} containing {count} supported files?\n\n"
                "Matching settings, API tokens and character/chat data will be overwritten. "
                "A safety backup of the current installation is created first. "
                "Older v2.5.1 backups are supported. Restart Soul of Waifu after restoring."
            ).format(version=source_version, count=count),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        result = manager.restore_backup(source)
        status = self.translations.get(
            "backup_restored_status", "Restored {count} files from backup version {version}."
        ).format(count=result.get("files_restored", 0), version=result.get("source_version", "unknown"))
        self.ui.label_backup_status.setText(status)
        QtWidgets.QMessageBox.information(
            self,
            self.translations.get("backup_restore_done_title", "Backup restored"),
            self.translations.get(
                "backup_restore_done_message",
                "Backup import completed.\n\nFiles restored: {count}\nDetected backup version: {version}\n\n"
                "Automatic safety backup of the pre-restore state:\n{backup}\n\n"
                "Please restart Soul of Waifu so all restored settings and characters are reloaded.",
            ).format(
                count=result.get("files_restored", 0),
                version=result.get("source_version", "unknown"),
                backup=result.get("automatic_backup", "unknown"),
            ),
        )

    def on_import_backup_clicked(self):
        """Import a Yume backup (.yumepack). Older formats (.sowpack, ZIP / .sowbackup of 2.5.x, no manifest) still work."""
        ctrl = self.ui.profile_backup_controller
        source, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.translations.get("backup_import_dialog_title", "Import Yume Backup"),
            ctrl._backup_dir(),
            "Yume Backup (*.yumepack *.sowpack);;Older backups (*.zip *.sowbackup);;All files (*.*)",
        )
        if not source:
            return
        try:
            from app.utils.profile_backup import read_manifest
            manifest, err = read_manifest(source)
            if manifest is not None and err in (None, "newer_version"):
                ctrl.load_preview(source)       # a real Yume backup: same restore (with safety snapshot) as the profile backup
                ctrl.start_restore()
                return
            self._restore_backup_from(source)   # older archives without a Yume manifest
        except (BackupError, OSError, ValueError) as exc:
            logger.exception("Backup import failed")
            QtWidgets.QMessageBox.critical(
                self,
                self.translations.get("backup_error_title", "Backup error"),
                str(exc),
            )
        except Exception as exc:
            logger.exception("Unexpected backup import error")
            QtWidgets.QMessageBox.critical(self, "Backup error", f"{type(exc).__name__}: {exc}")

    def on_import_backup_folder_clicked(self):
        """Import folder backups produced by older SoW installations."""
        source = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.translations.get("backup_import_folder_dialog_title", "Select old backup folder"),
            str(self._backup_manager().root),
        )
        if not source:
            return
        try:
            self._restore_backup_from(source)
        except (BackupError, OSError, ValueError) as exc:
            logger.exception("Legacy backup folder import failed")
            QtWidgets.QMessageBox.critical(
                self,
                self.translations.get("backup_error_title", "Backup error"),
                str(exc),
            )
        except Exception as exc:
            logger.exception("Unexpected legacy backup import error")
            QtWidgets.QMessageBox.critical(self, "Backup error", f"{type(exc).__name__}: {exc}")

    def on_comboBox_program_language_changed(self, index):
        self.configuration.update_main_setting("program_language", index)

        title = self.translations.get("language_changed_title", "Restart Required")
        first_text = self.translations.get("language_changed_body", "The program needs to be restarted for the changes to take effect.")
        second_text = self.translations.get("language_changed_question", "Would you like to restart the program now?")

        message_text = f"{first_text}\n\n{second_text}"

        parent_win = self.main_window if hasattr(self, "main_window") else self

        dialog = SowConfirmDialog(
            parent=parent_win,
            title=title,
            text=message_text,
            confirm_text="Restart",
            danger=False
        )

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            QtCore.QProcess.startDetached(sys.executable, sys.argv)
            QtCore.QCoreApplication.quit()

    def setup_interface_signals(self):
        """
        Connects signals for all UI elements to their respective handlers.
        """
        # PushButtons
        self.ui.pushButton_main.clicked.connect(self.interface_signals.on_pushButton_main_clicked)
        self.ui.pushButton_create_character_2.clicked.connect(self.interface_signals._prepare_blank_character_and_open_editor)
        self.ui.pushButton_create_character_3.clicked.connect(self.interface_signals.add_character_sync)
        self.ui.pushButton_characters_gateway.clicked.connect(self._on_characters_gateway_clicked)
        self.ui.pushButton_models_hub.clicked.connect(self.interface_signals.on_pushButton_models_hub_clicked)
        self.ui.pushButton_options.clicked.connect(self.interface_signals.on_pushButton_options_clicked)
        self.ui.pushButton_rp_editors.clicked.connect(self.on_rp_editors_clicked)
        self.ui.pushButton_soul_stage.clicked.connect(self.interface_signals._open_soul_stage_page)
        self.ui.about_btn.clicked.connect(self.interface_signals.set_about_program_button)
        self.ui.pushButton_youtube.clicked.connect(self.interface_signals.on_youtube)
        self.ui.pushButton_discord.clicked.connect(self.interface_signals.on_discord)
        self.ui.pushButton_github.clicked.connect(self.interface_signals.on_github)
        self.ui.btn_new_folder_menu.clicked.connect(self.interface_signals._open_create_folder_dialog)
        self.ui.btn_import_character_menu.clicked.connect(self.interface_signals.import_character_card_from_menu)
        self.ui.pushButton_stop_generation.clicked.connect(self.interface_signals.stop_generation)
        self.ui.pushButton_import_character_card.clicked.connect(self.interface_signals.import_character_card)
        self.ui.pushButton_export_character_card.clicked.connect(self.interface_signals.export_character_card)
        self.ui.pushButton_clean_character_card.clicked.connect(self.interface_signals.clean_character_card)
        self.ui.pushButton_import_character_image.clicked.connect(self.interface_signals.import_character_avatar)
        self.ui.pushButton_search_character.clicked.connect(self._on_search_characters_gateway_clicked)
        self.ui.pushButton_search_model.clicked.connect(self.interface_signals.start_search)
        self.ui.pushButton_models_hub_recommendations.clicked.connect(self.interface_signals.show_recommended_models)
        self.ui.pushButton_models_hub_popular.clicked.connect(self.interface_signals.show_popular_models)
        self.ui.pushButton_models_hub_my_models.clicked.connect(self.interface_signals.show_my_models)
        self.ui.pushButton_reload_models.clicked.connect(self.interface_signals.show_my_models)
        self.ui.pushButton_reload_bg_image.clicked.connect(self.interface_signals.load_background_images_to_comboBox)
        self.ui.pushButton_reload_ambient.clicked.connect(self.interface_signals.load_ambient_sound_to_comboBox)
        self.ui.lineEdit_search_character.returnPressed.connect(self._on_search_characters_gateway_clicked)
        self.ui.lineEdit_search_model.returnPressed.connect(self.interface_signals.start_search)
        self.ui.pushButton_author_notes.clicked.connect(self.interface_signals.open_author_notes_editor)
        self.ui.pushButton_change_chat_background.clicked.connect(self.interface_signals.open_chat_background_changer)
        self.ui.btn_open_character_editor.clicked.connect(self.interface_signals._prepare_blank_character_and_open_editor)
        self.ui.editor_character_list.itemClicked.connect(self.interface_signals.load_character_into_editor)
        self.ui.btn_create_new_character_editor.clicked.connect(self.interface_signals.prepare_new_character_editor)
        self.ui.btn_open_soul_stage.clicked.connect(self.interface_signals._open_soul_stage_page)
        self.ui.btn_open_personas.clicked.connect(self.interface_signals.open_personas_editor)
        self.ui.btn_open_lorebook.clicked.connect(self.interface_signals.open_lorebook_editor)
        self.ui.btn_open_discord_bot.clicked.connect(self.interface_signals.open_discord_gateway)
        self.ui.btn_open_prompts.clicked.connect(self.interface_signals.open_system_prompt_editor)
        self.ui.btn_open_image_gen.clicked.connect(self.interface_signals.open_image_gen_settings)
        self.ui.pushButton_soul_memory.clicked.connect(self.interface_signals.open_soul_memory_viewer)
        self.ui.pushButton_update_engine.clicked.connect(self.interface_signals.open_updater_dialog)
        self.ui.provider_group.buttonClicked.connect(self.interface_signals._on_provider_card_clicked)
        self.ui.btn_create_character_menu.clicked.connect(self.interface_signals._prepare_blank_character_and_open_editor)
        self.ui.pushButton_toggle_web_server.clicked.connect(self.interface_signals.on_toggle_web_server)
        self.ui.pushButton_create_backup.clicked.connect(self.on_create_backup_clicked)
        self.ui.pushButton_import_backup.clicked.connect(self.on_import_backup_clicked)
        self.ui.pushButton_import_backup_folder.clicked.connect(self.on_import_backup_folder_clicked)
        self.ui.comboBox_llm_presets.currentIndexChanged.connect(self.interface_signals.on_llm_preset_selected)
        self.ui.pushButton_llm_preset_save.clicked.connect(self.interface_signals.update_selected_llm_preset)
        self.ui.pushButton_llm_preset_save_as.clicked.connect(self.interface_signals.save_current_as_llm_preset)
        self.ui.pushButton_llm_preset_rename.clicked.connect(self.interface_signals.rename_selected_llm_preset)
        self.ui.pushButton_llm_preset_delete.clicked.connect(self.interface_signals.delete_selected_llm_preset)
        self.ui.pushButton_check_updates.clicked.connect(self.on_check_updates_clicked)
        self.ui.pushButton_open_release_page.clicked.connect(self.on_open_release_page_clicked)
        self.ui.lineEdit_update_repo.editingFinished.connect(self.on_update_repo_edited)
        self._init_updates_tab()
        self.ui.pushButton_copy_mobile_link.clicked.connect(self.interface_signals.on_copy_mobile_link)
        self.ui.pushButton_open_web_browser.clicked.connect(self.interface_signals.on_open_web_browser)
        self.ui.pushButton_ai_assistant.clicked.connect(self.interface_signals.open_ai_character_assistant)

        # ComboBoxes
        self.ui.comboBox_conversation_method.currentTextChanged.connect(self.interface_signals.on_comboBox_conversation_method_changed)
        self.ui.comboBox_local_llm_route.currentIndexChanged.connect(self.interface_signals.on_comboBox_local_llm_route_changed)
        self.ui.comboBox_program_language.currentIndexChanged.connect(self.on_comboBox_program_language_changed)
        self.ui.comboBox_input_devices.currentIndexChanged.connect(self.interface_signals.on_comboBox_input_devices_changed)
        self.ui.comboBox_output_devices.currentIndexChanged.connect(self.interface_signals.on_comboBox_output_devices_changed)
        self.ui.comboBox_translator.currentIndexChanged.connect(self.interface_signals.on_comboBox_translator_changed)
        self.ui.checkBox_auto_translate_new_messages.stateChanged.connect(self.interface_signals.on_checkBox_auto_translate_new_messages_stateChanged)
        self.ui.comboBox_target_language_translator.currentIndexChanged.connect(self.interface_signals.on_comboBox_target_language_translator_changed)
        self.ui.comboBox_conversation_method.currentIndexChanged.connect(self.interface_signals.update_api_token)
        self.ui.comboBox_live2d_mode.currentIndexChanged.connect(self.interface_signals.on_comboBox_live2d_mode_changed)
        self.ui.comboBox_model_fps.currentIndexChanged.connect(self.interface_signals.on_comboBox_model_fps_changed)
        self.ui.comboBox_model_background.currentIndexChanged.connect(self.interface_signals.on_comboBox_model_background_changed)
        self.ui.comboBox_model_bg_color.currentIndexChanged.connect(self.interface_signals.on_comboBox_model_bg_color_changed)
        self.ui.comboBox_model_bg_image.currentIndexChanged.connect(self.interface_signals.on_comboBox_model_bg_image_changed)
        self.ui.comboBox_ambient_mode.currentIndexChanged.connect(self.interface_signals.on_comboBox_ambient_mode_changed)
        self.ui.comboBox_llm_devices.currentIndexChanged.connect(self.interface_signals.on_comboBox_llm_devices_changed)
        self.ui.comboBox_llm_gpu_devices.currentIndexChanged.connect(self.interface_signals.on_comboBox_llm_gpu_devices_changed)
        self.ui.comboBox_chat_template.currentTextChanged.connect(self.interface_signals.on_comboBox_chat_template_changed)
        self.ui.comboBox_kv_cache.currentIndexChanged.connect(self.interface_signals.on_comboBox_kv_cache_changed)
        self.ui.comboBox_tts_voicing_mode.currentIndexChanged.connect(self.interface_signals.on_comboBox_tts_voicing_mode_changed)

        # LineEdits
        self.ui.lineEdit_api_token_options.textChanged.connect(self.interface_signals.save_api_token_in_real_time)
        self.ui.lineEdit_base_url_options.textChanged.connect(self.interface_signals.save_custom_url_in_real_time)
        self.ui.lineEdit_openai_model.textChanged.connect(self.interface_signals.save_openai_model_in_real_time)
        self.ui.lineEdit_remote_llm_model.textChanged.connect(self.interface_signals.save_remote_llm_model_in_real_time)
        self.ui.pushButton_test_remote_llm.clicked.connect(self.interface_signals.test_remote_llm_connection)
        self.ui.lineEdit_mistral_model.textChanged.connect(self.interface_signals.save_mistral_model_endpoint_in_real_time)
        self.ui.lineEdit_anthropic_model.textChanged.connect(self.interface_signals.save_anthropic_model_in_real_time)
        self.ui.lineEdit_gemini_model.textChanged.connect(self.interface_signals.save_gemini_model_in_real_time)
        self.ui.lineEdit_deepseek_model.textChanged.connect(self.interface_signals.save_deepseek_model_in_real_time)
        self.ui.lineEdit_grok_model.textChanged.connect(self.interface_signals.save_grok_model_in_real_time)
        self.ui.lineEdit_qwen_model.textChanged.connect(self.interface_signals.save_qwen_model_in_real_time)
        self.ui.lineEdit_zai_model.textChanged.connect(self.interface_signals.save_zai_model_in_real_time)
        self.ui.lineEdit_character_name_building.textChanged.connect(self.interface_signals.update_token_count)
        self.ui.textEdit_character_description_building.textChanged.connect(self.interface_signals.update_token_count)
        self.ui.textEdit_character_personality_building.textChanged.connect(self.interface_signals.update_token_count)
        self.ui.textEdit_first_message_building.textChanged.connect(self.interface_signals.update_token_count)
        self.ui.textEdit_scenario.textChanged.connect(self.interface_signals.update_token_count)
        self.ui.textEdit_example_messages.textChanged.connect(self.interface_signals.update_token_count)
        self.ui.textEdit_alternate_greetings.textChanged.connect(self.interface_signals.update_token_count)
        self.ui.lineEdit_gpuLayers.editingFinished.connect(self.interface_signals.update_gpu_layers_from_line_edit)
        self.ui.lineEdit_contextSize.editingFinished.connect(self.interface_signals.update_context_size_from_line_edit)
        self.ui.lineEdit_temperature.editingFinished.connect(self.interface_signals.update_temperature_from_line_edit)
        self.ui.lineEdit_topP.editingFinished.connect(self.interface_signals.update_top_p_from_line_edit)
        self.ui.lineEdit_maxTokens.editingFinished.connect(self.interface_signals.update_max_tokens_from_line_edit)
        self.ui.lineEdit_stop_strings.textChanged.connect(self.interface_signals.save_stop_strings_in_real_time)
        self.ui.lineEdit_freqPenalty.editingFinished.connect(self.interface_signals.update_freq_penalty_from_line_edit)
        self.ui.lineEdit_presPenalty.editingFinished.connect(self.interface_signals.update_pres_penalty_from_line_edit)
        self.ui.lineEdit_minP.editingFinished.connect(self.interface_signals.update_min_p_from_line_edit)
        self.ui.lineEdit_dynTempMin.editingFinished.connect(self.interface_signals.update_dyn_temp_min_from_line_edit)
        self.ui.lineEdit_dynTempMax.editingFinished.connect(self.interface_signals.update_dyn_temp_max_from_line_edit)
        self.ui.lineEdit_xtcProb.editingFinished.connect(self.interface_signals.update_xtc_prob_from_line_edit)
        self.ui.lineEdit_xtcThreshold.editingFinished.connect(self.interface_signals.update_xtc_threshold_from_line_edit)
        self.ui.lineEdit_dryMultiplier.editingFinished.connect(self.interface_signals.update_dry_multiplier_from_line_edit)
        self.ui.lineEdit_dryBase.editingFinished.connect(self.interface_signals.update_dry_base_from_line_edit)
        self.ui.lineEdit_dryAllowedLength.editingFinished.connect(self.interface_signals.update_dry_allowed_length_from_line_edit)
        self.ui.lineEdit_batchSize.editingFinished.connect(self.interface_signals.update_batch_size_from_line_edit)
        self.ui.lineEdit_cpuThreads.editingFinished.connect(self.interface_signals.update_cpu_threads_from_line_edit)
        self.ui.lineEdit_cpuMoeLayers.editingFinished.connect(self.interface_signals.update_cpu_moe_layers_from_line_edit)
        self.ui.lineEdit_customArgs.textChanged.connect(self.interface_signals.save_lineEdit_customArgs_in_real_time)
        self.ui.lineEdit_mcp_url.textChanged.connect(self.interface_signals.save_lineEdit_mcp_url_in_real_time)
        self.ui.pushButton_test_mcp_connection.clicked.connect(
            lambda: asyncio.create_task(self.interface_signals.test_mcp_connection())
        )
        self.ui.lineEdit_tts_custom_regex.textChanged.connect(self.interface_signals.save_tts_custom_regex_in_real_time)

        # Extended integrations, centralized AI service routing, and voice controls.
        self.ui.lineEdit_home_assistant_url.textChanged.connect(self.interface_signals.save_home_assistant_url)
        self.ui.lineEdit_home_assistant_token.textChanged.connect(self.interface_signals.save_home_assistant_token)
        self.ui.textEdit_home_assistant_entities.textChanged.connect(self.interface_signals.save_home_assistant_entities)
        self.ui.checkBox_home_assistant_enabled.toggled.connect(self.interface_signals.on_home_assistant_enabled_changed)
        self.ui.checkBox_home_assistant_allow_control.toggled.connect(self.interface_signals.on_home_assistant_control_changed)
        self.ui.pushButton_test_home_assistant.clicked.connect(
            lambda: asyncio.create_task(self.interface_signals.test_home_assistant_connection())
        )

        self.ui.checkBox_chat_tools_enabled.toggled.connect(self.interface_signals.on_chat_tools_enabled_changed)
        for tool_checkbox in (
            self.ui.checkBox_tool_web_search,
            self.ui.checkBox_tool_open_url,
            self.ui.checkBox_tool_system_info,
            self.ui.checkBox_tool_clipboard,
        ):
            tool_checkbox.toggled.connect(lambda _checked: self.interface_signals._save_tool_preferences())
        for hub_toggle in getattr(self.ui, "hub_tool_toggles", {}).values():
            hub_toggle.toggled.connect(lambda _checked: self.interface_signals._save_tool_preferences(from_hub=True))
        self.ui.checkBox_tool_program_launch.toggled.connect(self.interface_signals.on_program_launch_enabled_changed)
        self.ui.textEdit_tool_allowed_programs.textChanged.connect(self.interface_signals.save_allowed_programs)

        self.ui.comboBox_service_llm_route.currentIndexChanged.connect(self.interface_signals.on_service_llm_route_changed)
        self.ui.comboBox_whisper_device.currentIndexChanged.connect(self.interface_signals.save_whisper_device)
        self.ui.comboBox_whisper_gpu.currentIndexChanged.connect(self.interface_signals.save_whisper_gpu)
        self.ui.comboBox_qwen_default_gpu.currentIndexChanged.connect(self.interface_signals.save_qwen_default_gpu)
        self.ui.comboBox_vision_device.currentIndexChanged.connect(self.interface_signals.save_vision_device)
        self.ui.comboBox_vision_gpu.currentIndexChanged.connect(self.interface_signals.save_vision_gpu)
        self.ui.lineEdit_llm_cuda_gpu_indices.textChanged.connect(self.interface_signals.save_llm_gpu_indices)
        self.ui.pushButton_refresh_gpu_devices.clicked.connect(self.interface_signals.refresh_gpu_devices)
        for _mid, _w in self.ui.gpu_select_tools.items():
            _w.changed.connect(lambda v, m=_mid: self.interface_signals.on_tool_model_gpu_changed(m, v))
        self.ui.gpu_select_vision.changed.connect(self.interface_signals.on_vision_gpu_multi_changed)
        self.ui.gpu_select_whisper.changed.connect(self.interface_signals.on_whisper_gpu_multi_changed)
        self.ui.gpu_select_tts.changed.connect(self.interface_signals.on_tts_gpu_multi_changed)

        self.ui.checkBox_natural_dialogue.toggled.connect(
            lambda checked: self.interface_signals.configuration_settings.update_main_setting("natural_dialogue_enabled", bool(checked))
        )
        self.ui.checkBox_emotion_continuity.toggled.connect(
            lambda checked: self.interface_signals.configuration_settings.update_main_setting("emotion_continuity_enabled", bool(checked))
        )
        self.ui.checkBox_avoid_repetition.toggled.connect(
            lambda checked: self.interface_signals.configuration_settings.update_main_setting("avoid_repetitive_phrases", bool(checked))
        )
        self.ui.comboBox_dialogue_style.currentIndexChanged.connect(self.interface_signals.save_conversation_style)
        self.ui.spinBox_emotion_intensity.valueChanged.connect(self.interface_signals.save_emotion_intensity)
        self.ui.checkBox_wake_word_enabled.toggled.connect(
            lambda checked: self.interface_signals.configuration_settings.update_main_setting("wake_word_enabled", bool(checked))
        )
        self.ui.lineEdit_wake_word.textChanged.connect(self.interface_signals.save_wake_word)
        self.ui.spinBox_wake_word_timeout.valueChanged.connect(
            lambda value: self.interface_signals.configuration_settings.update_main_setting("wake_word_timeout_sec", int(value))
        )
        self.ui.comboBox_anti_echo_mode.currentIndexChanged.connect(
            lambda index: self.interface_signals.configuration_settings.update_main_setting("anti_echo_mode", self.ui.comboBox_anti_echo_mode.itemData(index) or "off")
        )
        self.ui.spinBox_aec_stream_delay.valueChanged.connect(
            lambda value: self.interface_signals.configuration_settings.update_main_setting("aec_stream_delay_ms", int(value))
        )
        self.ui.checkBox_aec_noise_suppression.toggled.connect(
            lambda checked: self.interface_signals.configuration_settings.update_main_setting("aec_noise_suppression", bool(checked))
        )
        self.ui.spinBox_anti_echo_tail.valueChanged.connect(
            lambda value: self.interface_signals.configuration_settings.update_main_setting("anti_echo_tail_ms", int(value))
        )
        self.ui.spinBox_voice_silence.valueChanged.connect(
            lambda value: self.interface_signals.configuration_settings.update_main_setting("voice_silence_ms", int(value))
        )
        self.ui.spinBox_voice_preroll.valueChanged.connect(
            lambda value: self.interface_signals.configuration_settings.update_main_setting("voice_preroll_ms", int(value))
        )
        self.ui.spinBox_tts_chunk_max_chars.valueChanged.connect(
            lambda value: self.interface_signals.configuration_settings.update_main_setting("tts_chunk_max_chars", int(value))
        )
        self.ui.spinBox_tts_chunk_pause_ms.valueChanged.connect(
            lambda value: self.interface_signals.configuration_settings.update_main_setting("tts_chunk_pause_ms", int(value))
        )
        self.ui.checkBox_lipsync_smoothing.toggled.connect(
            lambda checked: self.interface_signals.configuration_settings.update_main_setting("lipsync_smoothing", bool(checked))
        )
        
        # Sliders
        self.ui.gpu_layers_horizontalSlider.valueChanged.connect(self.interface_signals.save_gpu_layers_in_real_time)
        self.ui.context_size_horizontalSlider.valueChanged.connect(self.interface_signals.save_context_size_in_real_time)
        self.ui.temperature_horizontalSlider.valueChanged.connect(self.interface_signals.save_temperature_in_real_time)
        self.ui.top_p_horizontalSlider.valueChanged.connect(self.interface_signals.save_top_p_in_real_time)
        self.ui.max_tokens_horizontalSlider.valueChanged.connect(self.interface_signals.save_max_tokens_in_real_time)
        self.ui.spinBox_summary_interval.valueChanged.connect(self.interface_signals.save_interval_summary_in_real_time)
        self.ui.freq_penalty_horizontalSlider.valueChanged.connect(self.interface_signals.save_freq_penalty_in_real_time)
        self.ui.pres_penalty_horizontalSlider.valueChanged.connect(self.interface_signals.save_pres_penalty_in_real_time)
        self.ui.min_p_horizontalSlider.valueChanged.connect(self.interface_signals.save_min_p_in_real_time)
        self.ui.dyn_temp_min_horizontalSlider.valueChanged.connect(self.interface_signals.save_dyn_temp_min_in_real_time)
        self.ui.dyn_temp_max_horizontalSlider.valueChanged.connect(self.interface_signals.save_dyn_temp_max_in_real_time)
        self.ui.xtc_prob_horizontalSlider.valueChanged.connect(self.interface_signals.save_xtc_prob_in_real_time)
        self.ui.xtc_threshold_horizontalSlider.valueChanged.connect(self.interface_signals.save_xtc_threshold_in_real_time)
        self.ui.dry_multiplier_horizontalSlider.valueChanged.connect(self.interface_signals.save_dry_multiplier_in_real_time)
        self.ui.dry_base_horizontalSlider.valueChanged.connect(self.interface_signals.save_dry_base_in_real_time)
        self.ui.dry_allowed_length_horizontalSlider.valueChanged.connect(self.interface_signals.save_dry_allowed_length_in_real_time)
        self.ui.batch_size_horizontalSlider.valueChanged.connect(self.interface_signals.save_batch_size_in_real_time)
        self.ui.cpu_threads_horizontalSlider.valueChanged.connect(self.interface_signals.save_cpu_threads_in_real_time)
        self.ui.cpu_moe_layers_horizontalSlider.valueChanged.connect(self.interface_signals.save_cpu_moe_layers_in_real_time)
        
        # CheckBox
        self.ui.checkBox_enable_mlock.stateChanged.connect(self.interface_signals.on_checkBox_enable_mlock_stateChanged)
        self.ui.checkBox_enable_flash_attention.stateChanged.connect(self.interface_signals.on_checkBox_enable_flash_attention_stateChanged)
        self.ui.checkBox_enable_no_mmap.stateChanged.connect(self.interface_signals.on_checkBox_enable_no_mmap_stateChanged)
        self.ui.checkBox_enable_advanced_sampling.stateChanged.connect(self.interface_signals.on_checkBox_enable_advanced_sampling_stateChanged)
        self.ui.stackedWidget.currentChanged.connect(self.interface_signals.on_stacked_widget_changed)
        self.ui.checkBox_enable_nsfw.stateChanged.connect(self.interface_signals.on_checkBox_enable_nsfw_stateChanged)
        self.ui.checkBox_enable_ambient.stateChanged.connect(self.interface_signals.on_checkBox_enable_ambient_stateChanged)
        self.ui.checkBox_enable_sow_system.stateChanged.connect(self.interface_signals.on_checkBox_enable_sow_system_stateChanged)
        self.ui.checkBox_enable_soul_memory.stateChanged.connect(self.interface_signals.on_checkBox_enable_soul_memory_stateChanged)
        self.ui.checkBox_enable_summary.stateChanged.connect(self.interface_signals.on_checkBox_enable_summary_stateChanged)
        self.ui.checkBox_reasoning_mode.stateChanged.connect(self.interface_signals.on_checkBox_reasoning_mode_stateChanged)
        self.ui.comboBox_reasoning_effort.currentIndexChanged.connect(self.interface_signals.on_comboBox_reasoning_effort_changed)
        self.ui.checkBox_enable_tool_calling.stateChanged.connect(self.interface_signals.on_checkBox_enable_tool_calling_stateChanged)
        self.ui.checkBox_enable_mcp.stateChanged.connect(self.interface_signals.on_checkBox_enable_mcp_stateChanged)
        self.ui.checkBox_mcp_confirm_calls.toggled.connect(
            lambda checked: self.interface_signals.configuration_settings.update_main_setting("mcp_confirm_calls", bool(checked))
        )

        self.ui.anchor_menu_building.currentRowChanged.connect(self.interface_signals._scroll_character_creation)
        self.ui.scrollArea_character_building.verticalScrollBar().valueChanged.connect(self.interface_signals._update_anchor_menu_from_scroll)
        if hasattr(self.ui, 'pushButton_preview_prompt'):
            self.ui.pushButton_preview_prompt.clicked.connect(self.interface_signals._show_raw_prompt_preview)

    @asyncSlot()
    async def on_rp_editors_clicked(self):
        self.ui.pushButton_rp_editors.setChecked(True)
        index = self.ui.stackedWidget.indexOf(self.ui.rp_editors_page)
        self.ui.stackedWidget.setCurrentIndex(index)

    @asyncSlot()
    async def _on_characters_gateway_clicked(self):
        await self.interface_signals.open_characters_gateway()

    @asyncSlot()
    async def _on_search_characters_gateway_clicked(self):
        await self.interface_signals.search_character()

    def check_pc_specs(self):
        """
        Detects and displays basic PC specifications such as RAM and GPU info.
        """
        memory_info = psutil.virtual_memory()
        available_memory = round(memory_info.total / 1024 ** 3, 2)
        self.ui.ram_label.setText(f"{available_memory} GB RAM")

        gpu_info = self.translations.get("no_gpu", "No GPU")
        
        if torch.cuda.is_available():
            try:
                gpu_name = torch.cuda.get_device_name(0)
                gpu_properties = torch.cuda.get_device_properties(0)

                total_vram_gb = round(gpu_properties.total_memory / (1024 ** 3), 2) 
                
                gpu_info = f"{gpu_name} - {total_vram_gb} GB VRAM"
                
            except Exception as e:
                gpu_info = f"GPU detected, but info error: {str(e)}"
        else:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    gpu_name = gpu.name
                    gpu_vram_gb = round(gpu.memoryTotal / 1024, 2) 
                    gpu_info = f"{gpu_name} - {gpu_vram_gb} GB VRAM"
            except ImportError:
                pass
            except Exception as e:
                print(f"GPUtil detection failed: {e}")

        self.ui.gpu_label.setText(gpu_info)

        available_memory_round = memory_info.total // (1024 ** 3)
        self.configuration.update_main_setting("available_memory", available_memory_round)
        
    @staticmethod
    def _numeric_version_tuple(value):
        """Convert tags such as v2.5.3 into comparable integer tuples."""
        import re
        numbers = re.findall(r"\d+", str(value or ""))
        return tuple(int(part) for part in numbers[:4]) if numbers else (0,)

    def check_for_updates(self, current_version):
        try:
            from app.utils.branding import get_text as _brand_text
            _repo = _brand_text("update_repo") or "jofizcd/Soul-of-Waifu"
            repo_url = f"https://api.github.com/repos/{_repo}/releases/latest"
            response = requests.get(repo_url, timeout=10)
            response.raise_for_status()
            latest_release = response.json()
            latest_version = latest_release["tag_name"]

            # The upstream repository may still report an older tag than this
            # downstream 2.5.3 build. Do not offer a downgrade as an update.
            if self._numeric_version_tuple(latest_version) > self._numeric_version_tuple(current_version):
                logger.info(f"A newer version has been released: {latest_version}")
                return latest_version, latest_release["html_url"]
            return None, None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Couldn't check for updates: {e}")
            return None, None

        except Exception as e:
            logger.error(f"Error checking for updates: {e}", exc_info=True)
            return None, None

    def show_update_dialog(self, latest_version, github_url):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(self.translations.get("update_available_title", "Update Available"))
        dialog.setWindowIcon(QtGui.QIcon("app/gui/icons/logotype.ico"))
        dialog.setFixedSize(400, 450)

        dialog.setStyleSheet("""
            QDialog {
                background-color: rgb(27,27,27);
                border-radius: 20px;
            }
            QLabel#titleLabel {
                font-size: 22px;
                font-weight: 800;
                color: #ffffff;
                margin-top: 10px;
            }
            QLabel#infoLabel {
                font-size: 14px;
                color: #9CA3AF;
                line-height: 1.5;
            }
            QLabel#version_label {
                font-size: 12px;
                font-weight: bold;
                color: #6B7280;
                background-color: #1F1F23;
                padding: 4px 12px;
                border-radius: 10px;
            }
            QPushButton {
                padding: 12px 24px;
                font-size: 13px;
                font-weight: bold;
                border-radius: 12px;
            }
            QPushButton#github_button {
                background-color: #777778;
                color: white;
                border: none;
            }
            QPushButton#github_button:hover {
                background-color: #828282;
            }
            QPushButton#github_button:pressed {
                background-color: #909091;
            }
            QPushButton#close_button {
                background-color: transparent;
                color: #9CA3AF;
                border: 1px solid #374151;
            }
            QPushButton#close_button:hover {
                background-color: #1F1F23;
                color: white;
            }
        """)

        font = QtGui.QFont("Inter Tight Medium", 10)
        dialog.setFont(font)

        main_layout = QtWidgets.QVBoxLayout(dialog)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(10)

        icon_label = QtWidgets.QLabel()
        icon_pixmap = QtGui.QPixmap("app/gui/icons/reload.png").scaled(
            100, 100, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation
        )
        icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        title_label = QtWidgets.QLabel(
            self.translations.get("update_available_body", "New Update!")
        )
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        version_box = QtWidgets.QHBoxLayout()
        v_text = f"{current_version}  →  {latest_version}"
        version_label = QtWidgets.QLabel(v_text)
        version_label.setObjectName("version_label")
        version_box.addStretch()
        version_box.addWidget(version_label)
        version_box.addStretch()

        info_label = QtWidgets.QLabel(
            self.translations.get("update_available_info", 
            "A newer version of Soul of Waifu is ready. Update now to get the latest features and fixes.")
        )
        info_label.setObjectName("infoLabel")
        info_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        info_label.setWordWrap(True)

        button_layout = QtWidgets.QVBoxLayout()
        button_layout.setSpacing(10)
        button_layout.setContentsMargins(0, 20, 0, 0)

        github_button = QtWidgets.QPushButton(
            self.translations.get("update_available_link", "Update Now")
        )
        github_button.setObjectName("github_button")
        github_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        github_button.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(github_url)))

        close_button = QtWidgets.QPushButton(
            self.translations.get("update_available_close", "Later")
        )
        close_button.setObjectName("close_button")
        close_button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        close_button.clicked.connect(dialog.reject)

        button_layout.addWidget(github_button)
        button_layout.addWidget(close_button)

        main_layout.addWidget(icon_label)
        main_layout.addWidget(title_label)
        main_layout.addLayout(version_box)
        main_layout.addSpacing(5)
        main_layout.addWidget(info_label)
        main_layout.addStretch()
        main_layout.addLayout(button_layout)

        dialog.exec()

    def load_fonts_from_folder(self, folder_path):
        for font_file in os.listdir(folder_path):
            font_path = os.path.join(folder_path, font_file)
            if font_path.endswith(('.ttf', '.otf')):
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id == -1:
                    logger.error(f"Error loading font: {font_file}")
                else:
                    QFontDatabase.applicationFontFamilies(font_id)
    
    def create_size_grips(self):
        mw = self.ui.main_widget
        Edge = QtCore.Qt.Edge
        Cursor = QtCore.Qt.CursorShape

        def make(edges, cursor):
            grip = _EdgeResizeGrip(self, edges, cursor, parent=mw)
            grip.show()
            grip.raise_()
            return grip

        self.top_left_grip = make(Edge.TopEdge | Edge.LeftEdge, Cursor.SizeFDiagCursor)
        self.top_right_grip = make(Edge.TopEdge | Edge.RightEdge, Cursor.SizeBDiagCursor)
        self.bottom_left_grip = make(Edge.BottomEdge | Edge.LeftEdge, Cursor.SizeBDiagCursor)
        self.bottom_right_grip = make(Edge.BottomEdge | Edge.RightEdge, Cursor.SizeFDiagCursor)

        self.top_edge_grip = make(Edge.TopEdge, Cursor.SizeVerCursor)
        self.bottom_edge_grip = make(Edge.BottomEdge, Cursor.SizeVerCursor)
        self.left_edge_grip = make(Edge.LeftEdge, Cursor.SizeHorCursor)
        self.right_edge_grip = make(Edge.RightEdge, Cursor.SizeHorCursor)

        self._all_grips = [
            self.top_left_grip, self.top_right_grip,
            self.bottom_left_grip, self.bottom_right_grip,
            self.top_edge_grip, self.bottom_edge_grip,
            self.left_edge_grip, self.right_edge_grip,
        ]

    def update_size_grip_positions(self):
        mw = self.ui.main_widget
        w, h = mw.width(), mw.height()
        g = RESIZE_GRIP_SIZE

        self.top_left_grip.setGeometry(0, 0, g, g)
        self.top_right_grip.setGeometry(w - g, 0, g, g)
        self.bottom_left_grip.setGeometry(0, h - g, g, g)
        self.bottom_right_grip.setGeometry(w - g, h - g, g, g)

        self.top_edge_grip.setGeometry(g, 0, max(0, w - 2 * g), g)
        self.bottom_edge_grip.setGeometry(g, h - g, max(0, w - 2 * g), g)
        self.left_edge_grip.setGeometry(0, g, g, max(0, h - 2 * g))
        self.right_edge_grip.setGeometry(w - g, g, g, max(0, h - 2 * g))

        self._update_grips_visibility()

    def _update_grips_visibility(self):
        visible = not (self.isMaximized() or self.isFullScreen())
        for grip in getattr(self, "_all_grips", []):
            grip.setVisible(visible)

    def resizeEvent(self, event):
        current_widget = self.ui.stackedWidget.currentWidget()

        if current_widget == self.ui.main_characters_page:
            self.interface_signals.handle_resize(event)
        elif current_widget == self.ui.rp_editors_page:
            self.interface_signals.handle_rp_editors_resize(event)
        elif current_widget == self.ui.charactersgateway_page:
            self.interface_signals.handle_gate_resize(event)
        
        super().resizeEvent(event)

        self.update_size_grip_positions()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if event.pos().y() <= self.ui.frame_version.height():
                self.draggable = True
                self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if self.draggable:
            self.move(self.pos() + event.pos() - self.offset)

    def mouseReleaseEvent(self, event):
        self.draggable = False

    def toggle_maximize(self):
        if self.isMaximized():
            icon_maximize = QtGui.QIcon()
            icon_maximize.addPixmap(QtGui.QPixmap("app/gui/icons/maximize.png"), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
            self.ui.horizontalLayout_main_widget.setContentsMargins(0, 0, 0, 0)
            self.ui.maximize_btn.setIcon(icon_maximize)
            self.showNormal()
        else:
            self.ui.horizontalLayout_main_widget.setContentsMargins(0, 0, 0, 0)
            icon_maximize = QtGui.QIcon()
            icon_maximize.addPixmap(QtGui.QPixmap("app/gui/icons/maximize_minimize.png"), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
            self.ui.maximize_btn.setIcon(icon_maximize)
            self.showMaximized()

if __name__ == "__main__":
    if sys.platform == 'win32':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(taskbar_app_id())

    app = QApplication(sys.argv)
    app.setWindowIcon(build_app_icon())

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    try:
        from app.utils.asyncio_nesting import install as _install_nesting
        _install_nesting(loop)
    except Exception:
        logger.exception("asyncio nesting patch failed")
    
    _boot_progress(70, "window")
    try:
        from app.gui import yume_theme
        yume_theme.install_hook()
    except Exception:
        logger.exception("Yume theme hook failed")
    main_window = MainWindow()
    _boot_progress(88, "window")
    main_window.setWindowIcon(build_app_icon())
    fonts_folder = "app/font"
    main_window.load_fonts_from_folder(fonts_folder)
    try:
        yume_theme.restyle_window(main_window)
    except Exception:
        logger.exception("Yume theme could not be applied")

    try:
        from app.gui.yume_decor import fit_settings_pages
        fit_settings_pages(main_window.ui.tabWidget_options)
    except Exception:
        logger.exception("Could not fit the settings pages")
    main_window.show()
    try:
        main_window.ui.network_llm_controller.attach(main_window.interface_signals)
    except Exception:
        logger.exception("Network LLM controller could not be attached")
    try:
        main_window.ui.stt_language_controller.attach(main_window.interface_signals)
    except Exception:
        logger.exception("STT language controller could not be attached")
    try:
        main_window.ui.plain_text_controller.attach(main_window.interface_signals)
    except Exception:
        logger.exception("Plain text mode controller could not be attached")
    try:
        main_window.ui.android_pairing_controller.attach(main_window.interface_signals)
    except Exception:
        logger.exception("Android pairing controller could not be attached")
    try:
        main_window.ui.vision_remote_controller.attach(main_window.interface_signals)
    except Exception:
        logger.exception("Vision remote controller could not be attached")
    try:
        main_window.ui.image_settings_controller.attach(main_window.interface_signals)
    except Exception:
        logger.exception("Image settings controller could not be attached")
    try:
        main_window.ui.vrm_settings_controller.attach(main_window.interface_signals)
    except Exception:
        logger.exception("VRM settings controller could not be attached")
    try:
        main_window.ui.presets_controller.attach(main_window.interface_signals)
    except Exception:
        logger.exception("Presets controller could not be attached")
    try:
        main_window.ui.tool_log_controller.attach(main_window.interface_signals)
    except Exception:
        logger.exception("Tool log controller could not be attached")
    try:
        from app.gui.home_welcome import install_home_welcome
        install_home_welcome(main_window)
    except Exception:
        logger.exception("Welcome page could not be created")
    try:
        main_window.ui.profile_backup_controller.attach(main_window.interface_signals)
    except Exception:
        logger.exception("Profile backup controller could not be attached")
    try:
        main_window.ui.dashboard_controller.attach(main_window.interface_signals)
    except Exception:
        logger.exception("Dashboard controller could not be attached")
    try:
        main_window.ui.spotify_controller.attach(main_window.interface_signals)
    except Exception:
        logger.exception("Spotify controller could not be attached")
    try:
        main_window.ui.organizer_controller.attach(main_window.interface_signals)
    except Exception:
        logger.exception("Organizer controller could not be attached")
    try:
        from app.utils.pc_wake import PcWake
        main_window.interface_signals.pc_wake = PcWake(main_window.interface_signals)
        if main_window.interface_signals.configuration_settings.get_main_setting("pcwake_enabled"):
            QtCore.QTimer.singleShot(5000, main_window.interface_signals.pc_wake.start)
        app.aboutToQuit.connect(main_window.interface_signals.pc_wake.stop)
    except Exception:
        logger.exception("Hey Yume could not be prepared")
    try:
        asyncio.ensure_future(main_window.interface_signals.organizer_loop())
    except Exception:
        logger.exception("Reminder loop could not be started")
    try:
        from app.gui.yume_decor import SakuraLayer
        _cfg = main_window.interface_signals.configuration_settings
        _petals_on = _cfg.get_main_setting("yume_petals")
        _petals_on = True if _petals_on is None else bool(_petals_on)
        main_window.sakura_layer = SakuraLayer(main_window.ui.main_widget)
        main_window.sakura_layer.set_active(_petals_on)
        _chk = QtWidgets.QCheckBox(main_window.translations.get("settings_sakura_effect", "Sakura effect"))
        _chk.setChecked(_petals_on)
        _chk.setStyleSheet("QCheckBox { color: #B9A9C9; margin: 8px 12px 0 12px; } "
                           "QCheckBox::indicator:checked { background-color: #FF8FC7; border: 1px solid #FF8FC7; border-radius: 3px; } "
                           "QCheckBox::indicator:unchecked { background-color: transparent; border: 1px solid #8D7AA3; border-radius: 3px; }")
        _chk.toggled.connect(lambda on: (main_window.sakura_layer.set_active(on), _cfg.update_main_setting("yume_petals", bool(on))))
        main_window.ui.options_sidebar_layout.addWidget(_chk)
        main_window.sakura_checkbox = _chk
    except Exception:
        logger.exception("Sakura layer could not be created")
    _boot_progress(100, "ready")
    # Qt alone leaves a blank icon on the Windows taskbar for this window: set it natively too.
    apply_taskbar_icon(main_window)
    QtCore.QTimer.singleShot(1500, lambda: apply_taskbar_icon(main_window))

    current_version = "v3.0.0"

    class _UpdateBridge(QtCore.QObject):
        found = QtCore.pyqtSignal(str, str)

    update_bridge = _UpdateBridge()
    update_bridge.found.connect(main_window.show_update_dialog)

    def deferred_update_check():
        # Yume updates itself through the Yume Updater. The old GitHub check is only used when a repository is set in the branding
        # (it pointed at the original project and blocked the window for up to 10 s whenever GitHub could not be reached).
        try:
            from app.utils.branding import get_text as _brand_text
            if not _brand_text("update_repo"):
                return
        except Exception:
            return

        def work():
            latest_version, github_url = main_window.check_for_updates(current_version)
            if latest_version:
                update_bridge.found.emit(latest_version, github_url)

        threading.Thread(target=work, name="update-check", daemon=True).start()

    QtCore.QTimer.singleShot(0, deferred_update_check)
    
    asyncio.ensure_future(main_window.startup_sequence())

    _test_exec = os.environ.get("YUME_TEST_EXEC")      # developer aid: run a script inside the running app
    if _test_exec:
        def _run_test_exec():
            try:
                exec(compile(open(_test_exec, encoding="utf-8").read(), _test_exec, "exec"), {"main_window": main_window, "app": app, "QtCore": QtCore, "os": os})
            except Exception:
                logger.exception("YUME_TEST_EXEC failed")
        QtCore.QTimer.singleShot(int(os.environ.get("YUME_TEST_DELAY", "8000")), _run_test_exec)

    _shot_dir = os.environ.get("YUME_SHOT_DIR")
    if _shot_dir:
        if os.environ.get("YUME_SHOT_FULL"):
            main_window.resize(1350, 2600)
        # Developer aid: save a screenshot of every page / settings tab, then quit.
        def _take_shots():
            os.makedirs(_shot_dir, exist_ok=True)
            ui = main_window.ui
            _chat = os.environ.get("YUME_SHOT_CHAT")
            if _chat:
                asyncio.ensure_future(main_window.interface_signals.open_chat(_chat))
                def _chat_shot():
                    main_window.grab().save(os.path.join(_shot_dir, "chat.png"))
                    app.quit()
                QtCore.QTimer.singleShot(int(os.environ.get("YUME_SHOT_CHAT_WAIT", "7000")), _chat_shot)
                return
            shots = []
            for i in range(ui.stackedWidget.count()):
                shots.append((f"page{i}_{ui.stackedWidget.widget(i).objectName()}", ui.stackedWidget, i, None))
            options = getattr(ui, "tabWidget_options", None)
            if options is not None:
                for j in range(options.count()):
                    shots.append((f"options{j}_{options.widget(j).objectName()}", ui.stackedWidget,
                                  ui.stackedWidget.indexOf(ui.options_page), (options, j)))

            def step(n=0):
                if n >= len(shots):
                    app.quit()
                    return
                name, stack, idx, sub = shots[n]
                stack.setCurrentIndex(idx)
                if sub:
                    sub[0].setCurrentIndex(sub[1])
                def _snap(sub=sub, name=name, n=n):
                    target = main_window
                    target.grab().save(os.path.join(_shot_dir, name + ".png"))
                    step(n + 1)
                QtCore.QTimer.singleShot(600, _snap)
            step()
        QtCore.QTimer.singleShot(int(os.environ.get("YUME_SHOT_DELAY", "6000")), _take_shots)

    def _arm_exit_watchdog(seconds: float = 8.0):
        """The window is closed: background threads / the web engine / servers must not keep the process alive (a new start would then fail
        with "could not be started" because the old instance still holds its files and ports)."""
        import threading
        import time as _time

        def _kill():
            _time.sleep(seconds)
            try:
                # what kept the process alive? (written once to logs/exit_debug.log - helps to find the real cause)
                import sys as _sys
                import traceback as _tb
                frames = _sys._current_frames()
                lines = [_time.strftime("%Y-%m-%d %H:%M:%S") + " - still running after the window was closed:"]
                for th in threading.enumerate():
                    if th is threading.current_thread() or th is threading.main_thread():
                        continue
                    lines.append(f"  thread {th.name!r} daemon={th.daemon}")
                    if not th.daemon and th.ident in frames:
                        lines += ["    " + ln.rstrip() for ln in _tb.format_stack(frames[th.ident])[-4:]]
                with open(os.path.join("logs", "exit_debug.log"), "a", encoding="utf-8") as fh:
                    fh.write("\n".join(lines) + "\n")
            except Exception:
                pass
            try:
                logging.shutdown()
            except Exception:
                pass
            os._exit(0)
        threading.Thread(target=_kill, daemon=True, name="exit-watchdog").start()

    try:
        app.aboutToQuit.connect(_arm_exit_watchdog)
    except Exception:
        logger.exception("exit watchdog could not be connected")
    loop.run_forever()
    _arm_exit_watchdog(5.0)
