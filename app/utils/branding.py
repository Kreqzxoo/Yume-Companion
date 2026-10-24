"""Optional user branding overrides; safe defaults preserve upstream branding.

The data lives in ``app/configuration/branding.json`` and is edited by an
external tool; the application itself has no UI for it. Rules that keep the
file forward compatible:

* Every key is optional. A key that is *missing* uses the default below; a key
  that is present but empty (``""``) hides that element (links, author, ...).
* Unknown keys are ignored here and must be preserved by any editor.
* New fields are added to ``BRANDING_FIELDS`` only (plain literal data, so an
  external editor can read it with ``ast.literal_eval`` without importing this
  module). Older editors keep working because they preserve unknown keys.
"""
from __future__ import annotations
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRANDING_FILE = PROJECT_ROOT / "app" / "configuration" / "branding.json"

BRANDING_SCHEMA = 1

# group, key, label, type (text|multiline|url|image|repo), default
BRANDING_FIELDS = [
    {"group": "identity", "key": "app_name", "label": "Programmname", "type": "text", "default": "Yume Companion"},
    {"group": "identity", "key": "tagline", "label": "Untertitel im Startfenster (start.bat)", "type": "text", "default": "Soul Continuum"},
    {"group": "identity", "key": "banner_text", "label": "Großer Banner-Text im Startfenster (leer = Programmname)", "type": "text", "default": ""},
    {"group": "identity", "key": "short_name", "label": "Kurzname", "type": "text", "default": "SoW"},
    {"group": "identity", "key": "author_name", "label": "Autor / Made by", "type": "text", "default": "jofizcd"},
    {"group": "identity", "key": "author_url", "label": "Autor-Link", "type": "url", "default": "https://github.com/jofizcd"},
    {"group": "logos", "key": "app_icon_path", "label": "App-Icon (Taskleiste/Fenster, quadratisch, mind. 256x256)", "type": "image", "default": ""},
    {"group": "logos", "key": "logo_path", "label": "Programm-Logo (Fenster, Info-Dialog)", "type": "image", "default": ""},
    {"group": "logos", "key": "sidebar_logo_path", "label": "Seitenleisten-Logo (breit, optional)", "type": "image", "default": ""},
    {"group": "links", "key": "website_url", "label": "Website", "type": "url", "default": "https://jofizcd.github.io/soul-of-waifu-site/"},
    {"group": "links", "key": "docs_url", "label": "Dokumentation", "type": "url", "default": "https://jofizcd.github.io/soul-of-waifu-site/docs/"},
    {"group": "links", "key": "support_url", "label": "Unterstützen / Spenden", "type": "url", "default": "https://www.donationalerts.com/r/jofizcd"},
    {"group": "links", "key": "discord_url", "label": "Discord", "type": "url", "default": "https://discord.gg/6vFtQGVfxM"},
    {"group": "links", "key": "github_url", "label": "GitHub (Seitenleiste, Discord-Status)", "type": "url", "default": "https://github.com/jofizcd/Soul-of-Waifu"},
    {"group": "links", "key": "youtube_url", "label": "YouTube", "type": "url", "default": "https://www.youtube.com/@jofizcd"},
    {"group": "links", "key": "update_repo", "label": "Update-Repository (owner/name)", "type": "repo", "default": ""},
    {"group": "credits", "key": "about_description_html", "label": "Info-Text (HTML, leer = Standardtext)", "type": "multiline", "default": ""},
    {"group": "credits", "key": "additional_credits", "label": "Zusätzliche Credits", "type": "multiline", "default": ""},
]

_DEFAULTS = {f["key"]: f["default"] for f in BRANDING_FIELDS}


def load_branding() -> dict:
    try:
        data = json.loads(BRANDING_FILE.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_text(key: str, branding: dict | None = None) -> str:
    """Value of a branding key: default when missing, '' when deliberately empty."""
    data = load_branding() if branding is None else branding
    if key in data and isinstance(data[key], str):
        return data[key].strip()
    return str(_DEFAULTS.get(key, ""))


def get_url(key: str, branding: dict | None = None) -> str:
    """Like get_text, but only returns http(s) URLs."""
    value = get_text(key, branding)
    return value if value.lower().startswith(("https://", "http://")) else ""


def app_name(branding: dict | None = None) -> str:
    return get_text("app_name", branding) or str(_DEFAULTS["app_name"])


def resolve_branding_path(key: str = "logo_path") -> Path | None:
    branding = load_branding()
    raw = branding.get(key)
    if not raw:
        return None
    p = Path(str(raw))
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p.resolve() if p.exists() and p.is_file() else None


def app_icon_path() -> str:
    custom = resolve_branding_path("logo_path")
    fallback = PROJECT_ROOT / "app" / "gui" / "icons" / "logotype.ico"
    return str(custom or fallback)


ICON_SIZES = (16, 24, 32, 48, 64, 96, 128, 256)


def _square_image(image):
    """Make a QImage square. Wide/tall logos are centre-cropped (a letterboxed wide logo
    would shrink to a few pixels in the taskbar); nearly square images are padded."""
    from PyQt6 import QtCore, QtGui
    w, h = image.width(), image.height()
    ratio = max(w, h) / max(1, min(w, h))
    if ratio > 1.15:
        side = min(w, h)
        return image.copy((w - side) // 2, (h - side) // 2, side, side)
    side = max(w, h)
    canvas = QtGui.QImage(side, side, QtGui.QImage.Format.Format_ARGB32)
    canvas.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(canvas)
    painter.drawImage((side - w) // 2, (side - h) // 2, image)
    painter.end()
    return canvas


def build_app_icon():
    """QIcon for window + taskbar, built from the dedicated app icon (``app_icon_path``),
    else from the logo, else the bundled icon. Always square, in all common sizes."""
    from PyQt6 import QtCore, QtGui

    fallback = PROJECT_ROOT / "app" / "gui" / "icons" / "logotype.ico"
    custom = resolve_branding_path("app_icon_path") or resolve_branding_path("logo_path")
    if custom is None:
        return QtGui.QIcon(str(fallback))
    image = QtGui.QImage(str(custom))
    if image.isNull():
        return QtGui.QIcon(str(fallback))
    image = _square_image(image)
    icon = QtGui.QIcon()
    for size in ICON_SIZES:
        scaled = image.scaled(size, size, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                              QtCore.Qt.TransformationMode.SmoothTransformation)
        icon.addPixmap(QtGui.QPixmap.fromImage(scaled))
    return icon


def taskbar_app_id() -> str:
    """Windows taskbar identity. Upstream id for the original name, a separate id for
    a renamed build so Windows does not mix it up with (or cache the icon of) another SoW."""
    import re
    name = app_name()
    if name == _DEFAULTS["app_name"]:
        return "com.jofizcd.soul_of_waifu.v2"
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")[:40] or "custom"
    return f"com.sow.custom.{slug}"


def ensure_app_ico() -> str:
    """Path of a multi-size .ico for the Win32 taskbar: built from the app icon / logo
    (cached in app/cache, rebuilt when the source changes), else the bundled icon."""
    fallback = PROJECT_ROOT / "app" / "gui" / "icons" / "logotype.ico"
    src = resolve_branding_path("app_icon_path") or resolve_branding_path("logo_path")
    if src is None:
        return str(fallback)
    target = PROJECT_ROOT / "app" / "cache" / "app_icon.ico"
    stamp = target.with_suffix(".src")
    signature = f"{src}|{src.stat().st_mtime_ns}|{src.stat().st_size}"
    try:
        if target.is_file() and stamp.read_text(encoding="utf-8") == signature:
            return str(target)
    except OSError:
        pass
    from app.utils.taskbar import write_ico
    if not write_ico(src, target):
        return str(fallback)
    try:
        stamp.write_text(signature, encoding="utf-8")
    except OSError:
        pass
    return str(target)


def apply_taskbar_icon(window) -> bool:
    """Set the taskbar/window icon with Win32 as well as Qt (see app/utils/taskbar.py)."""
    try:
        from app.utils.taskbar import apply_native_icon
        return apply_native_icon(int(window.winId()), ensure_app_ico())
    except Exception:
        return False
