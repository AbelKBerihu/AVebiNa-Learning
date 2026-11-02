import os
import sys
import time
import wave
import threading
import queue
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import numpy as np
import sounddevice as sd

class AudioRecorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        on_level_update: Optional[Callable[[float], None]] = None
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_level_update = on_level_update

        self.is_recording = False
        self.is_paused = False
        self.start_time = 0.0
        self.elapsed_time = 0.0

        self._audio_queue: queue.Queue = queue.Queue()
        self._recorded_frames: List[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._stream_secondary: Optional[sd.InputStream] = None
        self._secondary_queue: queue.Queue = queue.Queue()

        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    @staticmethod
    def get_audio_devices() -> List[Dict[str, Any]]:
        """
        Returns a classified list of audio input devices on Windows, Linux, and macOS.
        """
        devices = []
        try:
            raw_devices = sd.query_devices()
            default_in = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else 0

            for idx, dev in enumerate(raw_devices):
                max_in = dev.get("max_input_channels", 0)
                name = dev.get("name", f"Device {idx}")
                hostapi = dev.get("hostapi", 0)

                # Identify if this is a system loopback / monitor (Meeting audio)
                is_loopback = False
                lower_name = name.lower()
                if any(k in lower_name for k in ["monitor", "loopback", "stereo mix", "what u hear", "cable output", "wave out", "sysdefault"]):
                    is_loopback = True

                category = "System / Meeting Audio" if is_loopback else "Microphone"
                is_default = (idx == default_in)

                if max_in > 0:
                    devices.append({
                        "id": idx,
                        "name": name,
                        "channels": max_in,
                        "hostapi": hostapi,
                        "category": category,
                        "is_loopback": is_loopback,
                        "is_default": is_default,
                        "display_name": f"[{category}] {name}" + (" (Default)" if is_default else "")
                    })
        except Exception as e:
            print(f"Error querying audio devices: {e}", file=sys.stderr)

        return devices

    def start_recording(self, device_id: Optional[int] = None, secondary_device_id: Optional[int] = None) -> bool:
        """
        Starts recording audio. If secondary_device_id is provided, both streams are recorded
        and mixed (e.g. Microphone + System Loopback simultaneously).
        """
        with self._lock:
            if self.is_recording:
                return True

            self._recorded_frames = []
            self._audio_queue = queue.Queue()
            self._secondary_queue = queue.Queue()
            self.is_recording = True
            self.is_paused = False
            self.start_time = time.time()
            self.elapsed_time = 0.0

            try:
                # Primary stream (e.g. System Loopback or Default Mic)
                try:
                    self._stream = sd.InputStream(
                        samplerate=self.sample_rate,
                        channels=self.channels,
                        dtype="int16",
                        device=device_id,
                        callback=self._audio_callback_primary
                    )
                    self._stream.start()
                except Exception as primary_err:
                    # If specific ALSA/WASAPI device failed to open, fall back to default audio server
                    if device_id is not None:
                        self._stream = sd.InputStream(
                            samplerate=self.sample_rate,
                            channels=self.channels,
                            dtype="int16",
                            device=None,
                            callback=self._audio_callback_primary
                        )
                        self._stream.start()
                    else:
                        raise primary_err

                # Secondary stream (optional mixed mic)
                if secondary_device_id is not None and secondary_device_id != device_id:
                    try:
                        self._stream_secondary = sd.InputStream(
                            samplerate=self.sample_rate,
                            channels=self.channels,
                            dtype="int16",
                            device=secondary_device_id,
                            callback=self._audio_callback_secondary
                        )
                        self._stream_secondary.start()
                    except Exception:
                        self._stream_secondary = None

                return True
            except Exception as e:
                self.is_recording = False
                print(f"Failed to start audio stream: {e}", file=sys.stderr)
                raise e

    def _audio_callback_primary(self, indata, frames, time_info, status):
        if not self.is_recording or self.is_paused:
            return

        data_copy = indata.copy()

        # If secondary stream is active, mix them
        if self._stream_secondary is not None:
            try:
                sec_chunk = self._secondary_queue.get_nowait()
                min_len = min(len(data_copy), len(sec_chunk))
                # Mix with headroom
                mixed = (0.5 * data_copy[:min_len].astype(np.float32) + 0.5 * sec_chunk[:min_len].astype(np.float32))
                data_copy[:min_len] = np.clip(mixed, -32768, 32767).astype(np.int16)
            except queue.Empty:
                pass

        self._audio_queue.put(data_copy)
        self._recorded_frames.append(data_copy)

        # Calculate RMS level for visual VU meter & waveform visualizer
        if self.on_level_update:
            try:
                float_data = data_copy.astype(np.float32) / 32768.0
                rms = np.sqrt(np.mean(float_data ** 2)) if len(float_data) > 0 else 0.0
                level = min(1.0, float(rms * 8.0))
                # Pass both level and raw chunk to the visualizer
                try:
                    self.on_level_update(level, data_copy)
                except TypeError:
                    self.on_level_update(level)
            except Exception:
                pass

    def _audio_callback_secondary(self, indata, frames, time_info, status):
        if not self.is_recording or self.is_paused:
            return
        self._secondary_queue.put(indata.copy())

    def pause_recording(self):
        with self._lock:
            if self.is_recording and not self.is_paused:
                self.is_paused = True

    def resume_recording(self):
        with self._lock:
            if self.is_recording and self.is_paused:
                self.is_paused = False

    def stop_recording(self, output_filepath: Optional[str] = None) -> Optional[str]:
        """
        Stops recording and saves accumulated audio to a standard WAV file.
        Returns the saved file path.
        """
        with self._lock:
            if not self.is_recording:
                return None

            self.is_recording = False
            self.is_paused = False

            for stream in [self._stream, self._stream_secondary]:
                if stream is not None:
                    try:
                        stream.stop()
                        stream.close()
                    except Exception:
                        pass
            self._stream = None
            self._stream_secondary = None

            if not self._recorded_frames:
                return None

            # Concatenate all recorded chunks
            all_audio = np.concatenate(self._recorded_frames, axis=0)

            if output_filepath is None:
                temp_dir = Path.home() / ".cache" / "cross-sync-notes" / "recordings"
                temp_dir.mkdir(parents=True, exist_ok=True)
                filename = f"meeting_recording_{int(time.time())}.wav"
                output_filepath = str(temp_dir / filename)

            # Ensure parent dir exists
            Path(output_filepath).parent.mkdir(parents=True, exist_ok=True)

            with wave.open(output_filepath, "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(all_audio.tobytes())

            return output_filepath
