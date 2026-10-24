import os
import logging
import threading
import numpy as np
import soundfile as sf
import sounddevice as sd

from PyQt6 import QtCore

logger = logging.getLogger("Ambient Player Client")

class AmbientPlayer(QtCore.QThread):
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)

    def __init__(self, file_path, device_index=None, volume=0.5):
        super().__init__()
        self.file_path = file_path
        self.device_index = device_index
        self.volume = float(volume if volume <= 1.0 else volume / 100.0)
        
        self._is_running = True
        self._raw_data = None
        self._samplerate = None
        self._current_pos = 0
        self._stop_event = threading.Event()

    def set_volume(self, volume: float):
        val = float(volume)
        if val > 1.0:
            val = val / 100.0
        self.volume = max(0.0, min(1.0, val))

    def set_device(self, index):
        self.device_index = index

    def stop_audio(self):
        self._is_running = False
        self._stop_event.set()

    def stop(self):
        self.stop_audio()

    def run(self):
        self._stop_event.clear()
        self._is_running = True
        self._current_pos = 0

        try:
            if not self.file_path or not os.path.exists(self.file_path):
                return

            data, samplerate = sf.read(self.file_path, dtype='float32')

            if data.ndim == 1:
                data = data.reshape(-1, 1)

            channels = data.shape[1]

            peak = np.max(np.abs(data))
            if peak > 0:
                data = data / peak

            self._raw_data = data
            self._samplerate = samplerate
            data_len = len(self._raw_data)

            def audio_callback(outdata, frames, time_info, status):
                if not self._is_running or self._stop_event.is_set():
                    outdata.fill(0)
                    raise sd.CallbackStop()

                chunk_len = frames
                end_pos = self._current_pos + chunk_len

                if end_pos <= data_len:
                    chunk = self._raw_data[self._current_pos:end_pos]
                    self._current_pos = end_pos if end_pos < data_len else 0
                else:
                    part1 = self._raw_data[self._current_pos:data_len]
                    remain = chunk_len - len(part1)
                    part2 = self._raw_data[0:remain]
                    chunk = np.concatenate((part1, part2), axis=0)
                    self._current_pos = remain

                outdata[:] = chunk * self.volume

            with sd.OutputStream(
                samplerate=self._samplerate,
                device=self.device_index,
                channels=channels,
                dtype='float32',
                callback=audio_callback
            ):
                self._stop_event.wait()

        except Exception as e:
            logger.debug(f"Ambient stream closed: {e}")
        finally:
            self._is_running = False
            self.finished.emit()