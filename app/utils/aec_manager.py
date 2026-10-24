"""WebRTC AEC3 installation, initialization and health checks for SoW 2.5.3."""
from __future__ import annotations
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple

logger = logging.getLogger("AEC Dependency")
AEC_PACKAGE = "pywebrtc-audio==0.2.0"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"


def probe_aec_installation() -> Tuple[bool, str]:
    """Import, construct and process a short silent buffer to verify the native extension."""
    try:
        import numpy as np
        from pywebrtc_audio import AudioProcessor
        settings = {}
        try:
            import json
            with (PROJECT_ROOT / "app" / "configuration" / "settings.json").open("r", encoding="utf-8") as f:
                main = json.load(f).get("main_settings", {})
                settings = main if isinstance(main, dict) else {}
        except Exception:
            pass
        delay = max(0, min(250, int(settings.get("aec_stream_delay_ms", 60) or 0)))
        ns = bool(settings.get("aec_noise_suppression", True))
        processor = AudioProcessor(
            sample_rate=16000,
            num_channels=1,
            echo_cancellation=True,
            noise_suppression=ns,
            auto_gain_control=False,
            stream_delay_ms=delay,
        )
        frame = np.zeros(160, dtype=np.int16)
        cleaned = processor.process(frame, frame)
        if not isinstance(cleaned, np.ndarray) or cleaned.shape != frame.shape:
            return False, "AEC3-Modul wurde importiert, aber der Audioprozessor lieferte ein unerwartetes Ergebnis."
        return True, f"WebRTC AEC3 bereit (pywebrtc-audio 0.2.0; Python: {sys.executable})."
    except Exception as exc:
        return False, f"WebRTC AEC3 nicht einsatzbereit: {type(exc).__name__}: {exc}"


def install_aec_dependency() -> Tuple[bool, str]:
    """Install the pinned AEC wheel into the currently running SoW Python environment."""
    before, detail = probe_aec_installation()
    if before:
        return True, detail
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "aec-install.log"
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-warn-script-location", AEC_PACKAGE]
    try:
        result = subprocess.run(
            cmd, cwd=str(PROJECT_ROOT), text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=300, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        output = (result.stdout or "")
        log_path.write_text(
            f"Command: {' '.join(cmd)}\nPython: {sys.executable}\nExit code: {result.returncode}\n\n{output}\n",
            encoding="utf-8",
        )
        if result.returncode != 0:
            message = f"pip-Installation fehlgeschlagen (Exit-Code {result.returncode}). Log: {log_path}\n" + output[-1800:]
            logger.error(message)
            return False, message
    except subprocess.TimeoutExpired as exc:
        output = str(exc)
        try: log_path.write_text(output, encoding="utf-8")
        except Exception: pass
        return False, f"Zeitüberschreitung beim Installieren von WebRTC AEC3 (5 Minuten). Log: {log_path}"
    except Exception as exc:
        return False, f"AEC-Installation konnte nicht gestartet werden: {type(exc).__name__}: {exc}"

    # Re-probe using this very same interpreter after pip has finished.
    ok, detail = probe_aec_installation()
    with log_path.open("a", encoding="utf-8") as f:
        f.write("\nPost-install probe: " + detail + "\n")
    if not ok:
        return False, f"pip wurde ausgeführt, aber die AEC3-Prüfung schlägt weiterhin fehl. Log: {log_path}\n{detail}"
    return True, detail
