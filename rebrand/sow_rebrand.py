"""SoW Rebrand - standalone branding editor for Soul of Waifu installations.

Private helper: it is not part of Soul of Waifu and has no entry inside the app.
It only writes ``app/configuration/branding.json`` and images below
``assets/custom_branding/`` of the chosen Soul of Waifu folder.

Forward compatible by design:
  * The editable fields are read from the target's ``app/utils/branding.py``
    (``BRANDING_FIELDS``, parsed with ``ast.literal_eval``, never executed).
    New SoW versions that add fields show up here automatically.
  * Keys this tool does not know are kept untouched (see tab "Weitere Schlüssel").
  * Without a registry (older/other versions) a built-in field list is used.

Run:  SoW-Rebrand.bat   (or: python sow_rebrand.py [path-to-SoW-folder])
Needs only Python 3 + PyQt6.
"""
from __future__ import annotations

import ast
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))
from banner_font import render_banner  # noqa: E402
SETTINGS_FILE = TOOL_DIR / "rebrand_settings.json"
BACKUP_DIR = TOOL_DIR / "backups"
PROFILE_DIR = TOOL_DIR / "profiles"
ASSET_REL = "assets/custom_branding"
MAX_IMAGE_BYTES = 20 * 1024 * 1024
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
START_CMD = "app/configuration/branding_start.cmd"
START_BANNER = "app/configuration/branding_banner.txt"
START_HOOK_MARK = "branding_start.cmd"
DEFAULT_NAME = "Soul of Waifu"
DEFAULT_TAGLINE = "Soul Continuum"
UNSAFE_CMD_CHARS = re.compile(r'[\x00-\x1f"%!^&|<>]')


def cmd_safe(text: str, limit: int = 60) -> str:
    """Make a value safe for `set "VAR=..."` in a batch file."""
    return UNSAFE_CMD_CHARS.sub("", text).strip()[:limit]


def banner_lines(text: str) -> list[str]:
    """Block-letter banner for text; plain text if no character is renderable."""
    lines = render_banner(text, 100)
    return lines if lines else [cmd_safe(text) or DEFAULT_NAME]

GROUP_TITLES = {
    "identity": "Name & Autor",
    "logos": "Logos",
    "links": "Links",
    "credits": "Texte & Credits",
}
GROUP_ORDER = ["identity", "logos", "links", "credits"]

# Used when the target has no BRANDING_FIELDS registry (older versions).
FALLBACK_FIELDS = [
    {"group": "identity", "key": "app_name", "label": "Programmname", "type": "text", "default": "Soul of Waifu"},
    {"group": "logos", "key": "logo_path", "label": "Programm-Logo", "type": "image", "default": ""},
    {"group": "credits", "key": "additional_credits", "label": "Zusätzliche Credits", "type": "multiline", "default": ""},
]


# ----------------------------------------------------------------- helpers
def read_json(path: Path, default):
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data
    except Exception:
        return default


def write_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    tmp.replace(path)


def is_sow_folder(path: Path) -> bool:
    return (path / "main.py").is_file() and (path / "app" / "configuration").is_dir()


def load_registry(target: Path):
    """Return (fields, schema, source) from the target's branding.py without executing it."""
    src = target / "app" / "utils" / "branding.py"
    try:
        tree = ast.parse(src.read_text(encoding="utf-8-sig"))
        fields, schema = None, 1
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name == "BRANDING_FIELDS":
                    fields = ast.literal_eval(node.value)
                elif name == "BRANDING_SCHEMA":
                    schema = int(ast.literal_eval(node.value))
        if isinstance(fields, list) and fields and all(isinstance(f, dict) and "key" in f for f in fields):
            return fields, schema, "Registry der Ziel-Version"
    except Exception:
        pass
    return FALLBACK_FIELDS, 1, "eingebaute Standardliste (Ziel hat keine Registry)"


def target_version(target: Path) -> str:
    try:
        return (target / "VERSION.txt").read_text(encoding="utf-8").strip() or "?"
    except OSError:
        return "?"


# ----------------------------------------------------------------- widgets
class FieldRow(QtWidgets.QWidget):
    """One branding field. 'Standard' = key absent, otherwise own value ('' hides)."""

    def __init__(self, field: dict, target: Path, parent=None):
        super().__init__(parent)
        self.field = field
        self.key = field["key"]
        self.ftype = field.get("type", "text")
        self.target = target
        self.default = str(field.get("default", ""))
        self.pending_image: Path | None = None

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 6)
        head = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel(f"<b>{field.get('label', self.key)}</b>  <span style='color:#888'>({self.key})</span>")
        head.addWidget(label, 1)
        self.use_default = QtWidgets.QCheckBox("Standard verwenden")
        self.use_default.setChecked(True)
        self.use_default.toggled.connect(self._refresh)
        head.addWidget(self.use_default)
        lay.addLayout(head)

        if self.ftype == "multiline":
            self.edit = QtWidgets.QPlainTextEdit()
            self.edit.setFixedHeight(110)
            self.edit.setPlaceholderText(self.default)
        elif self.ftype == "image":
            self.edit = QtWidgets.QLineEdit()
            self.edit.setReadOnly(True)
        else:
            self.edit = QtWidgets.QLineEdit()
            self.edit.setPlaceholderText(self.default)
        lay.addWidget(self.edit)

        if self.ftype == "image":
            row = QtWidgets.QHBoxLayout()
            self.preview = QtWidgets.QLabel()
            self.preview.setFixedSize(120, 120)
            self.preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.preview.setStyleSheet("border: 1px dashed #666; background: #222;")
            self.btn_pick = QtWidgets.QPushButton("Bild wählen…")
            self.btn_pick.clicked.connect(self._pick_image)
            row.addWidget(self.preview)
            row.addWidget(self.btn_pick)
            row.addStretch(1)
            lay.addLayout(row)
        else:
            hint = {"url": "Nur http(s)-Links. Leer lassen = Element ausblenden.",
                    "repo": "Format: owner/name. Leer lassen = Funktion aus.",
                    "multiline": "Leer lassen = nichts anzeigen."}.get(self.ftype, "Leer lassen = ausblenden.")
            note = QtWidgets.QLabel(f"<span style='color:#888'>{hint}  Standard: {self.default or '(leer)'}</span>")
            note.setWordWrap(True)
            lay.addWidget(note)
        self._refresh()

    # -- state ------------------------------------------------------------
    def _refresh(self):
        custom = not self.use_default.isChecked()
        if self.ftype == "image":
            self.btn_pick.setEnabled(custom)
        else:
            self.edit.setEnabled(custom)

    def _text(self) -> str:
        return self.edit.toPlainText() if self.ftype == "multiline" else self.edit.text()

    def _set_text(self, value: str):
        if self.ftype == "multiline":
            self.edit.setPlainText(value)
        else:
            self.edit.setText(value)

    def load(self, branding: dict):
        if self.key in branding and isinstance(branding[self.key], str):
            self.use_default.setChecked(False)
            self._set_text(branding[self.key])
        else:
            self.use_default.setChecked(True)
            self._set_text("" if self.ftype != "image" else "")
        if self.ftype == "image":
            self._update_preview(self._resolve(self.edit.text()))
        self._refresh()

    def _resolve(self, rel: str) -> Path | None:
        if not rel:
            return None
        p = Path(rel)
        p = p if p.is_absolute() else self.target / p
        return p if p.is_file() else None

    def _pick_image(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Bild wählen", str(Path.home()), "Bilder (*.png *.jpg *.jpeg *.bmp *.webp *.ico)")
        if not filename:
            return
        path = Path(filename)
        if path.stat().st_size > MAX_IMAGE_BYTES:
            QtWidgets.QMessageBox.warning(self, "Bild", "Die Datei ist größer als 20 MB.")
            return
        if QtGui.QImage(str(path)).isNull():
            QtWidgets.QMessageBox.warning(self, "Bild", "Das Bild konnte nicht gelesen werden.")
            return
        self.pending_image = path
        self.edit.setText(f"{ASSET_REL}/{self.key}.png")
        self._update_preview(path)
        if self.is_icon():
            img = QtGui.QImage(str(path))
            if img.width() != img.height():
                QtWidgets.QMessageBox.information(
                    self, "App-Icon",
                    "Das Bild ist nicht quadratisch. Es wird beim Speichern in der Mitte quadratisch zugeschnitten.\n"
                    "Am besten ein quadratisches Bild (mind. 256x256) ohne viel leeren Rand verwenden.")

    def _update_preview(self, path: Path | None):
        pix = QtGui.QPixmap(str(path)) if path else QtGui.QPixmap()
        if not pix.isNull() and self.is_icon():
            pix = QtGui.QPixmap.fromImage(self.squared(pix.toImage()))
        if pix.isNull():
            self.preview.setText("(Standard)" if self.use_default.isChecked() else "(kein Bild)")
            self.preview.setPixmap(QtGui.QPixmap())
        else:
            self.preview.setPixmap(pix.scaled(116, 116, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                              QtCore.Qt.TransformationMode.SmoothTransformation))

    # -- output -------------------------------------------------------------
    def validate(self) -> str:
        """Return an error text, or '' when fine."""
        if self.use_default.isChecked():
            return ""
        value = self._text().strip()
        if self.ftype == "url" and value and not value.lower().startswith(("https://", "http://")):
            return f"{self.field.get('label', self.key)}: nur http(s)-Links erlaubt."
        if self.ftype == "repo" and value and not REPO_RE.match(value):
            return f"{self.field.get('label', self.key)}: Format owner/name erwartet."
        return ""

    def value(self):
        """None = key absent (default). Otherwise the string to store."""
        if self.use_default.isChecked():
            return None
        return self._text().strip() if self.ftype != "multiline" else self._text().strip()

    def effective(self) -> str:
        return self.default if self.use_default.isChecked() else self._text().strip()

    def is_icon(self) -> bool:
        return self.key.endswith("icon_path")

    @staticmethod
    def squared(image: QtGui.QImage, max_side: int = 512) -> QtGui.QImage:
        """Centre-crop to a square (taskbar icons must be square) and cap the size."""
        side = min(image.width(), image.height())
        image = image.copy((image.width() - side) // 2, (image.height() - side) // 2, side, side)
        if side > max_side:
            image = image.scaled(max_side, max_side, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                 QtCore.Qt.TransformationMode.SmoothTransformation)
        return image

    def commit_image(self):
        """Copy a freshly picked image into the target as PNG."""
        if self.ftype != "image" or not self.pending_image:
            return
        dest = self.target / ASSET_REL / f"{self.key}.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        image = QtGui.QImage(str(self.pending_image))
        if not image.isNull() and self.is_icon():
            image = self.squared(image)
        if image.isNull() or not image.save(str(dest), "PNG"):
            raise RuntimeError(f"Bild für {self.key} konnte nicht gespeichert werden.")
        self.pending_image = None


# ----------------------------------------------------------------- main window
class RebrandWindow(QtWidgets.QMainWindow):
    def __init__(self, start_target: Path | None = None):
        super().__init__()
        self.setWindowTitle("SoW Rebrand")
        self.resize(900, 760)
        self.target: Path | None = None
        self.rows: list[FieldRow] = []
        self.schema = 1

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)

        top = QtWidgets.QHBoxLayout()
        self.target_edit = QtWidgets.QLineEdit()
        self.target_edit.setReadOnly(True)
        btn_choose = QtWidgets.QPushButton("SoW-Ordner wählen…")
        btn_choose.clicked.connect(self.choose_target)
        btn_open = QtWidgets.QPushButton("Ordner öffnen")
        btn_open.clicked.connect(self.open_target)
        top.addWidget(QtWidgets.QLabel("Ziel:"))
        top.addWidget(self.target_edit, 1)
        top.addWidget(btn_choose)
        top.addWidget(btn_open)
        root.addLayout(top)

        self.info_label = QtWidgets.QLabel("")
        self.info_label.setWordWrap(True)
        root.addWidget(self.info_label)

        self.tabs = QtWidgets.QTabWidget()
        root.addWidget(self.tabs, 1)

        bottom = QtWidgets.QHBoxLayout()
        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.setMinimumWidth(180)
        btn_profile_load = QtWidgets.QPushButton("Profil laden")
        btn_profile_load.clicked.connect(self.load_profile)
        btn_profile_save = QtWidgets.QPushButton("Als Profil speichern…")
        btn_profile_save.clicked.connect(self.save_profile)
        btn_reset = QtWidgets.QPushButton("Auf Original zurücksetzen")
        btn_reset.clicked.connect(self.reset_to_original)
        btn_save = QtWidgets.QPushButton("Speichern")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.save)
        bottom.addWidget(QtWidgets.QLabel("Profile:"))
        bottom.addWidget(self.profile_combo)
        bottom.addWidget(btn_profile_load)
        bottom.addWidget(btn_profile_save)
        bottom.addStretch(1)
        bottom.addWidget(btn_reset)
        bottom.addWidget(btn_save)
        root.addLayout(bottom)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        settings = read_json(SETTINGS_FILE, {})
        candidates = [start_target,
                      Path(settings["last_target"]) if settings.get("last_target") else None,
                      TOOL_DIR.parent]
        for cand in candidates:
            if cand and is_sow_folder(cand):
                self.set_target(cand)
                break
        else:
            self.info_label.setText("Bitte einen Soul-of-Waifu-Ordner wählen (enthält main.py).")
        self.refresh_profiles()

    # ---- target -------------------------------------------------------------
    def choose_target(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Soul-of-Waifu-Ordner wählen",
                                                            str(self.target or TOOL_DIR.parent))
        if not folder:
            return
        path = Path(folder)
        if not is_sow_folder(path):
            QtWidgets.QMessageBox.warning(self, "Ordner", "Das ist kein Soul-of-Waifu-Ordner (main.py oder app/configuration fehlt).")
            return
        self.set_target(path)

    def open_target(self):
        if self.target:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.target)))

    def set_target(self, path: Path):
        self.target = path
        self.target_edit.setText(str(path))
        try:
            SETTINGS_FILE.write_text(json.dumps({"last_target": str(path)}, indent=2), encoding="utf-8")
        except OSError:
            pass
        self.build_form()

    @property
    def branding_file(self) -> Path:
        return self.target / "app" / "configuration" / "branding.json"

    def build_form(self):
        fields, self.schema, source = load_registry(self.target)
        branding = read_json(self.branding_file, {})
        if not isinstance(branding, dict):
            branding = {}
        self.info_label.setText(
            f"Version im Ziel: <b>{target_version(self.target)}</b> · Felder: {len(fields)} aus {source} · "
            f"Datei: {self.branding_file.relative_to(self.target)}")

        self.tabs.clear()
        self.rows = []
        groups: dict[str, list[dict]] = {}
        for f in fields:
            groups.setdefault(f.get("group", "other"), []).append(f)
        ordered = [g for g in GROUP_ORDER if g in groups] + [g for g in groups if g not in GROUP_ORDER]
        for g in ordered:
            page = QtWidgets.QWidget()
            lay = QtWidgets.QVBoxLayout(page)
            for f in groups[g]:
                row = FieldRow(f, self.target)
                row.load(branding)
                self.rows.append(row)
                lay.addWidget(row)
            lay.addStretch(1)
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.tabs.addTab(scroll, GROUP_TITLES.get(g, g.capitalize()))

        self.build_banner_tab()
        known = {f["key"] for f in fields} | {"schema"}
        extra = {k: v for k, v in branding.items() if k not in known}
        self.extra_edit = QtWidgets.QPlainTextEdit(json.dumps(extra, ensure_ascii=False, indent=4))
        wrap = QtWidgets.QWidget()
        wl = QtWidgets.QVBoxLayout(wrap)
        wl.addWidget(QtWidgets.QLabel(
            "Schlüssel, die dieses Programm nicht kennt (z. B. von neueren Versionen). "
            "Sie bleiben beim Speichern erhalten; hier als JSON bearbeitbar."))
        wl.addWidget(self.extra_edit)
        self.tabs.addTab(wrap, "Weitere Schlüssel")
        self.status.setText("")

    # ---- start window (start.bat) -----------------------------------------------
    def start_hook_present(self) -> bool:
        try:
            return START_HOOK_MARK in (self.target / "start.bat").read_text(encoding="utf-8-sig", errors="ignore")
        except OSError:
            return False

    def build_banner_tab(self):
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        self.banner_note = QtWidgets.QLabel("")
        self.banner_note.setWordWrap(True)
        lay.addWidget(self.banner_note)
        self.banner_preview = QtWidgets.QPlainTextEdit()
        self.banner_preview.setReadOnly(True)
        self.banner_preview.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(9)
        self.banner_preview.setFont(font)
        self.banner_preview.setStyleSheet("background:#0c0c0c; color:#4bb8ff;")
        lay.addWidget(self.banner_preview, 1)
        self.tabs.addTab(page, "Startfenster")
        for row in self.rows:
            if row.key in ("app_name", "banner_text", "tagline"):
                row.use_default.toggled.connect(self.update_banner_preview)
                row.edit.textChanged.connect(self.update_banner_preview)
        self.update_banner_preview()

    def start_values(self):
        vals = {r.key: r for r in self.rows}
        name = cmd_safe(vals["app_name"].effective()) if "app_name" in vals else DEFAULT_NAME
        name = name or DEFAULT_NAME
        tagline = cmd_safe(vals["tagline"].effective()) if "tagline" in vals else DEFAULT_TAGLINE
        banner = cmd_safe(vals["banner_text"].effective()) if "banner_text" in vals else ""
        return name, tagline, (banner or name)

    def update_banner_preview(self, *_):
        if not hasattr(self, "banner_preview"):
            return
        name, tagline, banner = self.start_values()
        lines = banner_lines(banner)
        header = f"   {name} v{target_version(self.target)} {'- ' + tagline if tagline else ''}"
        self.banner_preview.setPlainText("\n".join(["  " + l for l in lines] + ["", header]))
        if self.start_hook_present():
            self.banner_note.setText("Vorschau des Startfensters (start.bat). Wird beim Speichern in "
                                     f"{START_CMD} und {START_BANNER} geschrieben.")
        else:
            self.banner_note.setText("<b>Hinweis:</b> Die start.bat dieser Version hat keinen Branding-Hook "
                                     "und wird nicht geändert; das Startfenster bleibt original.")

    def write_start_files(self):
        """Create/remove the derived files that start.bat/installer.bat read."""
        cmd_file = self.target / START_CMD
        banner_file = self.target / START_BANNER
        if not self.start_hook_present():
            return
        name, tagline, banner = self.start_values()
        is_default = (name == DEFAULT_NAME and tagline == DEFAULT_TAGLINE and banner == DEFAULT_NAME)
        if is_default:
            for p in (cmd_file, banner_file):
                try:
                    p.unlink()
                except FileNotFoundError:
                    pass
            return
        lines = banner_lines(banner)
        banner_file.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
        cmd = [f'set "BRAND_NAME={name}"',
               f'set "BRAND_TAGLINE={"- " + tagline if tagline else ""}"',
               'set "BRAND_BANNER=%~dp0branding_banner.txt"']
        cmd_file.write_bytes(("\r\n".join(cmd) + "\r\n").encode("utf-8"))

    # ---- save / reset -------------------------------------------------------
    def collect(self) -> dict:
        for row in self.rows:
            err = row.validate()
            if err:
                raise ValueError(err)
        try:
            extra = json.loads(self.extra_edit.toPlainText() or "{}")
            if not isinstance(extra, dict):
                raise ValueError
        except ValueError:
            raise ValueError("„Weitere Schlüssel“ ist kein gültiges JSON-Objekt.")
        data = dict(extra)
        data["schema"] = self.schema
        for row in self.rows:
            value = row.value()
            if value is not None:
                data[row.key] = value
        return data

    def write(self, data: dict):
        BACKUP_DIR.mkdir(exist_ok=True)
        if self.branding_file.exists():
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(self.branding_file, BACKUP_DIR / f"branding-{stamp}.json")
        for row in self.rows:
            row.commit_image()
        write_json_atomic(self.branding_file, data)
        self.write_start_files()

    def save(self):
        if not self.target:
            return
        try:
            data = self.collect()
            self.write(data)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Speichern", str(exc))
            return
        self.status.setText(f"Gespeichert: {self.branding_file}. Soul of Waifu neu starten, damit es wirkt. "
                            f"(Sicherung in {BACKUP_DIR.name}/)")

    def reset_to_original(self):
        if not self.target:
            return
        if QtWidgets.QMessageBox.question(
                self, "Zurücksetzen",
                "Alle bekannten Branding-Werte entfernen (zurück zum Original-Aussehen)?\n"
                "Unbekannte Schlüssel bleiben erhalten.") != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        for row in self.rows:
            row.use_default.setChecked(True)
            row.pending_image = None
        self.save()

    # ---- profiles -----------------------------------------------------------
    def refresh_profiles(self):
        self.profile_combo.clear()
        if PROFILE_DIR.is_dir():
            for p in sorted(PROFILE_DIR.iterdir()):
                if (p / "branding.json").is_file():
                    self.profile_combo.addItem(p.name)

    def save_profile(self):
        if not self.target:
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Profil", "Name des Profils:")
        name = re.sub(r"[^\w .-]", "_", name.strip()) if ok else ""
        if not name:
            return
        try:
            data = self.collect()
            dest = PROFILE_DIR / name
            if dest.exists():
                shutil.rmtree(dest)
            (dest / "images").mkdir(parents=True)
            for row in self.rows:
                if row.ftype == "image" and row.key in data and data[row.key]:
                    src = row.pending_image or row._resolve(data[row.key])
                    if src and Path(src).is_file():
                        shutil.copy2(src, dest / "images" / f"{row.key}{Path(src).suffix}")
                        data[row.key] = f"{ASSET_REL}/{row.key}.png"
            write_json_atomic(dest / "branding.json", data)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Profil", str(exc))
            return
        self.refresh_profiles()
        self.profile_combo.setCurrentText(name)
        self.status.setText(f"Profil „{name}“ gespeichert.")

    def load_profile(self):
        name = self.profile_combo.currentText()
        if not self.target or not name:
            return
        src = PROFILE_DIR / name
        data = read_json(src / "branding.json", None)
        if not isinstance(data, dict):
            return
        for row in self.rows:
            if row.key in data and isinstance(data[row.key], str):
                row.use_default.setChecked(False)
                row._set_text(data[row.key])
                if row.ftype == "image":
                    img = next((src / "images").glob(f"{row.key}.*"), None)
                    if img:
                        row.pending_image = img
                        row._update_preview(img)
            else:
                row.use_default.setChecked(True)
        known = {r.key for r in self.rows} | {"schema"}
        self.extra_edit.setPlainText(json.dumps({k: v for k, v in data.items() if k not in known},
                                                ensure_ascii=False, indent=4))
        self.status.setText(f"Profil „{name}“ geladen – noch nicht gespeichert.")


def main():
    app = QtWidgets.QApplication(sys.argv)
    start = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    win = RebrandWindow(start)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
