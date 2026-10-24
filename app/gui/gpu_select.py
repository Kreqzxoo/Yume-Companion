"""Multi-select GPU chooser (one checkbox per graphics card) and per-tool-model GPU assignment for the AI services page."""
from __future__ import annotations

import logging

from PyQt6 import QtCore, QtWidgets

logger = logging.getLogger("GpuSelect")


def list_gpus() -> list[tuple[int, str]]:
    try:
        import torch
        if torch.cuda.is_available():
            return [(i, torch.cuda.get_device_name(i)) for i in range(torch.cuda.device_count())]
    except Exception as exc:
        logger.debug("GPU enumeration failed: %s", exc)
    return []


def normalize(value) -> str:
    parts = [p.strip() for p in str(value or "").split(",") if p.strip().isdigit()]
    return ",".join(dict.fromkeys(parts))


class GpuMultiSelect(QtWidgets.QWidget):
    """Row of checkboxes, value = comma separated CUDA indices ('' = nothing selected)."""
    changed = QtCore.pyqtSignal(str)

    def __init__(self, parent=None, empty_text="Keine CUDA-GPU gefunden"):
        super().__init__(parent)
        self._empty_text = empty_text
        self._value = ""
        self._boxes: dict[int, QtWidgets.QCheckBox] = {}
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self.refresh()

    def refresh(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._boxes = {}
        gpus = list_gpus()
        if not gpus:
            lbl = QtWidgets.QLabel(self._empty_text)
            lbl.setStyleSheet("color: rgba(232,222,240,0.6); background: transparent; border: none;")
            self._layout.addWidget(lbl)
            return
        selected = set(self._value.split(",")) if self._value else set()
        for idx, name in gpus:
            cb = QtWidgets.QCheckBox(f"GPU {idx}: {name}")
            cb.setChecked(str(idx) in selected)
            cb.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            try:
                from app.gui.yume_decor import _unify_font
                _unify_font(cb)
            except Exception:
                pass
            cb.toggled.connect(self._on_toggled)
            self._boxes[idx] = cb
            self._layout.addWidget(cb)

    def _on_toggled(self, _checked):
        self._value = ",".join(str(i) for i, cb in sorted(self._boxes.items()) if cb.isChecked())
        self.changed.emit(self._value)

    def value(self) -> str:
        return self._value

    def set_value(self, value):
        value = normalize(value)
        self._value = value
        selected = set(value.split(",")) if value else set()
        for idx, cb in self._boxes.items():
            cb.blockSignals(True)
            cb.setChecked(str(idx) in selected)
            cb.blockSignals(False)


def tool_model_gpu_map(settings) -> dict:
    data = settings.get_main_setting("tool_model_gpus")
    return data if isinstance(data, dict) else {}


def gpu_override_for_model(settings, model_path) -> str | None:
    """CUDA indices configured for a downloaded tool model (matched by file name), else None."""
    try:
        import os
        from app.gui.agent_models import AGENT_MODELS
        name = os.path.basename(str(model_path or "")).lower()
        for entry in AGENT_MODELS:
            if entry["file"].lower() == name:
                value = normalize(tool_model_gpu_map(settings).get(entry["id"], ""))
                return value or None
    except Exception as exc:
        logger.debug("tool model gpu lookup failed: %s", exc)
    return None


def setting_indices(settings, plural_key, legacy_key="", default="0") -> str:
    """Saved GPU list ('0,1'); falls back to the old single-index setting."""
    value = normalize(settings.get_main_setting(plural_key))
    if value:
        return value
    if legacy_key:
        legacy = settings.get_main_setting(legacy_key)
        if legacy is not None and str(legacy).strip().isdigit():
            return str(int(legacy))
    return default


def freest_gpu(indices) -> int | None:
    """Of the selected CUDA GPUs, the one with the most free memory right now (None if CUDA is unavailable)."""
    try:
        import torch
        if not torch.cuda.is_available():
            return None
        count = torch.cuda.device_count()
        cands = [i for i in indices if 0 <= i < count] or list(range(count))
        best, best_free = None, -1
        for i in cands:
            try:
                free = torch.cuda.mem_get_info(i)[0]
            except Exception:
                free = 0
            if free > best_free:
                best, best_free = i, free
        return best
    except Exception:
        return None
