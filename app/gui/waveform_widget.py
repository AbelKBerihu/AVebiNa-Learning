import math
import numpy as np
from typing import List, Optional
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont

class WaveformWidget(QWidget):
    """
    A high-sensitivity real-time audio oscilloscope & waveform visualizer.
    Features automatic gain boost (AGC) so meeting audio (Google Meet, Zoom)
    and microphone speech visibly bounce and wave across the bar.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setMinimumWidth(280)

        self.is_recording = False
        self.raw_level = 0.0
        self.boosted_level = 0.0
        self.phase = 0.0
        self.recent_samples = np.zeros(64, dtype=np.float32)

    @property
    def level(self) -> float:
        return self.raw_level

        # 40 FPS refresh timer for fluid 60-hz-like animation
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(25)
        self.anim_timer.timeout.connect(self._animate_frame)
        self.anim_timer.start()

    def set_recording_state(self, is_recording: bool):
        self.is_recording = is_recording
        if not is_recording:
            self.raw_level = 0.0
            self.boosted_level = 0.0
            self.recent_samples.fill(0)
        self.update()

    def update_audio_data(self, level: float, raw_chunk: Optional[np.ndarray] = None):
        """Called when new audio samples arrive from the recorder callback."""
        try:
            val = max(0.0, min(1.0, float(level)))
            self.raw_level = val

            # High-Sensitivity Dynamic Auto-Gain:
            # Browser and Google Meet audio levels are often soft (~0.01 - 0.05).
            # Square-root expansion + 4x boost makes soft speech visibly wave!
            self.boosted_level = min(1.0, math.sqrt(val) * 3.8 + val * 2.0)

            if raw_chunk is not None and len(raw_chunk) > 0:
                arr = np.asarray(raw_chunk, dtype=np.float32)
                if arr.ndim > 1:
                    arr = np.mean(arr, axis=1)
                float_chunk = arr / 32768.0

                step = max(1, len(float_chunk) // 64)
                sampled = np.abs(float_chunk[::step][:64])
                if len(sampled) == 64:
                    # Apply gain boost to raw sample visualization
                    boosted_samples = np.clip(np.sqrt(sampled) * 3.5, 0.0, 1.0)
                    self.recent_samples = (0.5 * self.recent_samples + 0.5 * boosted_samples).astype(np.float32)
        except Exception:
            pass

    def _animate_frame(self):
        self.phase += 0.20
        if self.phase > 2 * math.pi:
            self.phase -= 2 * math.pi
        self.update()

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            w = self.width()
            h = self.height()
            mid_y = h / 2.0

            # Background box
            bg_rect = self.rect()
            painter.setPen(QPen(QColor("#334155"), 1))
            painter.setBrush(QBrush(QColor("#090d16")))
            painter.drawRoundedRect(bg_rect, 8, 8)

            if not self.is_recording:
                # Idle state: Subtle dashed centerline
                painter.setPen(QPen(QColor("#475569"), 1, Qt.PenStyle.DashLine))
                painter.drawLine(12, int(mid_y), w - 12, int(mid_y))

                painter.setPen(QColor("#64748b"))
                font = QFont("sans-serif", 10)
                painter.setFont(font)
                painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, "Ready to listen (Sound waves will bounce when playing)")
                return

            # Active Recording: Mirrored dynamic waveform bars
            num_bars = 52
            bar_spacing = (w - 24) / float(num_bars)
            max_bar_h = (h - 22) / 2.0

            active_level = max(self.boosted_level, float(np.mean(self.recent_samples)))

            for i in range(num_bars):
                idx = int((i / num_bars) * len(self.recent_samples))
                val = self.recent_samples[idx] if 0 <= idx < len(self.recent_samples) else 0.0
                sample_val = float(np.mean(val)) if hasattr(val, '__len__') else float(val)

                # Oscillating wave ripple envelope
                wave_mod = float(0.4 + 0.6 * math.sin(self.phase + (i * 0.35)))
                
                # Minimum lively height when recording so it's always breathing
                min_h = 4.0 + 2.5 * math.sin(self.phase * 1.5 + i * 0.2)
                amp = max(sample_val * 1.2, active_level * 0.9)
                bar_height = float(max(min_h, amp * max_bar_h * wave_mod))

                x = 12 + i * bar_spacing
                top_y = mid_y - bar_height
                bot_y = mid_y + bar_height

                # Gradient color: Cyan -> Emerald Green -> Orange/Red on vocal peaks
                if active_level > 0.65:
                    bar_color = QColor("#f43f5e")  # red peak
                elif active_level > 0.25:
                    bar_color = QColor("#38bdf8")  # vibrant cyan
                else:
                    bar_color = QColor("#10b981")  # lively emerald green

                painter.setPen(QPen(bar_color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(int(x), int(top_y), int(x), int(bot_y))

            # Centerline glow pulse
            painter.setPen(QPen(QColor(56, 189, 248, 90), 1))
            painter.drawLine(12, int(mid_y), w - 12, int(mid_y))

            # Pulsing Red Recording Indicator
            pulse_alpha = int(180 + 75 * math.sin(self.phase * 2))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(239, 68, 68, pulse_alpha))
            painter.drawEllipse(12, 10, 8, 8)

            painter.setPen(QColor("#f87171"))
            font = QFont("sans-serif", 9, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(26, 18, "LIVE RECORDING")
        except Exception:
            pass
