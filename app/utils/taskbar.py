"""Windows taskbar icon helpers.

Qt sets the window icon, but for some windows (frameless, layered, heavy widgets) the
Windows taskbar keeps showing a generic blank icon. These helpers set the icon with
plain Win32 calls as well: ICO file + WM_SETICON + window-class icon + (when pywin32
is available) the per-window property store that the taskbar reads first.
"""
from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from pathlib import Path

logger = logging.getLogger("Taskbar")

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
WM_SETICON = 0x0080
ICON_SMALL, ICON_BIG = 0, 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x10
GCLP_HICONSM, GCLP_HICON = -34, -14
SM_CXICON, SM_CXSMICON = 11, 49


def write_ico(source_png: str | Path, target_ico: str | Path) -> bool:
    """Create a multi-size square .ico from an image (wide images are centre-cropped)."""
    try:
        from PIL import Image
        img = Image.open(source_png).convert("RGBA")
        w, h = img.size
        ratio = max(w, h) / max(1, min(w, h))
        if ratio > 1.15:
            side = min(w, h)
            img = img.crop(((w - side) // 2, (h - side) // 2, (w - side) // 2 + side, (h - side) // 2 + side))
        else:
            side = max(w, h)
            canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            canvas.paste(img, ((side - w) // 2, (side - h) // 2))
            img = canvas
        if img.size[0] < 256:
            img = img.resize((256, 256), Image.Resampling.LANCZOS)
        Path(target_ico).parent.mkdir(parents=True, exist_ok=True)
        img.save(target_ico, format="ICO", sizes=ICO_SIZES)
        return True
    except Exception as exc:
        logger.warning("Could not write icon file %s: %s", target_ico, exc)
        return False


def apply_native_icon(hwnd: int, ico_path: str | Path) -> bool:
    """Set big/small window icon and class icon with Win32. Returns True on success."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.SetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        path = str(ico_path)
        big_px, small_px = user32.GetSystemMetrics(SM_CXICON), user32.GetSystemMetrics(SM_CXSMICON)
        big = user32.LoadImageW(None, path, IMAGE_ICON, big_px, big_px, LR_LOADFROMFILE)
        small = user32.LoadImageW(None, path, IMAGE_ICON, small_px, small_px, LR_LOADFROMFILE)
        if not big or not small:
            return False
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big)
        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small)
        user32.SetClassLongPtrW(hwnd, GCLP_HICON, big)
        user32.SetClassLongPtrW(hwnd, GCLP_HICONSM, small)
        return True
    except Exception as exc:
        logger.warning("Native icon call failed: %s", exc)
        return False


def apply_taskbar_identity(hwnd: int, app_id: str, ico_path: str | Path, display_name: str = "") -> bool:
    """Per-window taskbar properties (AppUserModelID + relaunch icon) via pywin32, if present."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        from win32com.propsys import propsys, pscon
        store = propsys.SHGetPropertyStoreForWindow(int(hwnd), propsys.IID_IPropertyStore)
        store.SetValue(pscon.PKEY_AppUserModel_ID, propsys.PROPVARIANTType(app_id))
        store.SetValue(pscon.PKEY_AppUserModel_RelaunchIconResource, propsys.PROPVARIANTType(f"{ico_path},0"))
        if display_name:
            store.SetValue(pscon.PKEY_AppUserModel_RelaunchDisplayNameResource, propsys.PROPVARIANTType(display_name))
        # RelaunchCommand is required for the icon/name to be honoured.
        store.SetValue(pscon.PKEY_AppUserModel_RelaunchCommand,
                       propsys.PROPVARIANTType(f'"{sys.executable}" "{Path(sys.argv[0]).resolve()}"'))
        store.Commit()
        return True
    except Exception as exc:
        logger.debug("Property store not applied: %s", exc)
        return False
