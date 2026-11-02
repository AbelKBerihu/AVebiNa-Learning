import time
import wave
import threading
from pathlib import Path
from typing import Optional, Callable
import numpy as np
import sounddevice as sd

class AudioPlayer:
    def __init__(self, on_progress: Optional[Callable[[float, float], None]] = None, on_finished: Optional[Callable[[], None]] = None):
        self.on_progress = on_progress
        self.on_finished = on_finished

        self.audio_data: Optional[np.ndarray] = None
        self.sample_rate: int = 16000
        self.channels: int = 1
        self.total_seconds: float = 0.0
        self.current_frame: int = 0

        self.is_playing: bool = False
        self._stream: Optional[sd.OutputStream] = None
        self._lock = threading.Lock()

    def load_file(self, filepath: str) -> bool:
        self.stop()
        path = Path(filepath)
        if not path.exists():
            return False

        try:
            with wave.open(str(path), "rb") as wf:
                self.channels = wf.getnchannels()
                self.sample_rate = wf.getframerate()
                sampwidth = wf.getsampwidth()
                nframes = wf.getnframes()
                raw_bytes = wf.readframes(nframes)

                if sampwidth == 2:
                    dtype = np.int16
                elif sampwidth == 1:
                    dtype = np.uint8
                elif sampwidth == 4:
                    dtype = np.int32
                else:
                    dtype = np.int16

                audio = np.frombuffer(raw_bytes, dtype=dtype)
                if self.channels > 1:
                    audio = audio.reshape(-1, self.channels)

                self.audio_data = audio
                self.total_seconds = nframes / float(self.sample_rate)
                self.current_frame = 0
                return True
        except Exception as e:
            print(f"Error loading WAV audio for playback: {e}")
            return False

    def play(self) -> bool:
        with self._lock:
            if self.audio_data is None or len(self.audio_data) == 0:
                return False

            if self.is_playing:
                return True

            self.is_playing = True
            try:
                self._stream = sd.OutputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype="int16",
                    callback=self._playback_callback
                )
                self._stream.start()
                return True
            except Exception as e:
                self.is_playing = False
                print(f"Failed to start playback stream: {e}")
                return False

    def pause(self):
        with self._lock:
            if self.is_playing and self._stream:
                self.is_playing = False
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None

    def stop(self):
        with self._lock:
            self.is_playing = False
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            self.current_frame = 0
            if self.on_progress:
                self.on_progress(0.0, self.total_seconds)

    def seek(self, target_seconds: float):
        with self._lock:
            if self.total_seconds <= 0:
                return
            target_frame = int(target_seconds * self.sample_rate)
            total_frames = len(self.audio_data)
            self.current_frame = max(0, min(target_frame, total_frames))
            if self.on_progress:
                self.on_progress(target_seconds, self.total_seconds)

    def _playback_callback(self, outdata, frames, time_info, status):
        if not self.is_playing or self.audio_data is None:
            outdata.fill(0)
            return

        total_frames = len(self.audio_data)
        remaining = total_frames - self.current_frame

        if remaining <= 0:
            outdata.fill(0)
            self.is_playing = False
            if self.on_finished:
                self.on_finished()
            return

        chunk_size = min(frames, remaining)
        chunk = self.audio_data[self.current_frame : self.current_frame + chunk_size]

        if self.channels == 1 and outdata.ndim == 2:
            outdata[:chunk_size, 0] = chunk.reshape(-1)
            if outdata.shape[1] > 1:
                outdata[:chunk_size, 1] = chunk.reshape(-1)
        else:
            outdata[:chunk_size] = chunk

        if chunk_size < frames:
            outdata[chunk_size:].fill(0)

        self.current_frame += chunk_size
        current_sec = self.current_frame / float(self.sample_rate)

        if self.on_progress:
            self.on_progress(current_sec, self.total_seconds)
