import math
import numpy as np
from typing import List, Optional
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QFont

class WaveformWidget(QWidget):
    """
    A real-time animated audio oscilloscope & waveform visualizer.
    Draws mirrored dynamic frequency wave bars and live oscilloscope curves
    that react directly to meeting speech and microphone sound.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(75)
        self.setMinimumWidth(260)

        self.is_recording = False
        self.level = 0.0
        self.phase = 0.0
        self.recent_samples = np.zeros(64, dtype=np.float32)

        # 40 FPS refresh timer for fluid animation
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(25)  # 40 fps
        self.anim_timer.timeout.connect(self._animate_frame)
        self.anim_timer.start()

    def set_recording_state(self, is_recording: bool):
        self.is_recording = is_recording
        if not is_recording:
            self.level = 0.0
            self.recent_samples.fill(0)
        self.update()

    def update_audio_data(self, level: float, raw_chunk: Optional[np.ndarray] = None):
        """Called when new audio samples arrive from the recorder callback."""
        self.level = max(0.0, min(1.0, float(level)))
        if raw_chunk is not None and len(raw_chunk) > 0:
            try:
                # Downsample chunk to 64 points
                float_chunk = raw_chunk.astype(np.float32) / 32768.0
                step = max(1, len(float_chunk) // 64)
                sampled = float_chunk[::step][:64]
                if len(sampled) == 64:
                    self.recent_samples = 0.6 * self.recent_samples + 0.4 * np.abs(sampled)
            except Exception:
                pass

    def _animate_frame(self):
        self.phase += 0.15
        if self.phase > 2 * math.pi:
            self.phase -= 2 * math.pi
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        mid_y = h / 2.0

        # Background rounded box
        bg_rect = self.rect()
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.setBrush(QBrush(QColor("#090d16")))
        painter.drawRoundedRect(bg_rect, 8, 8)

        if not self.is_recording:
            # Idle state: Subtle glowing centerline
            painter.setPen(QPen(QColor("#475569"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(10, int(mid_y), w - 10, int(mid_y))

            painter.setPen(QColor("#64748b"))
            font = QFont("sans-serif", 10)
            painter.setFont(font)
            painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, "Ready to listen (Sound waves will display here)")
            return

        # Active Recording: Mirrored dynamic waveform bars & glow curve
        num_bars = 48
        bar_spacing = (w - 24) / float(num_bars)
        max_bar_h = (h - 18) / 2.0

        for i in range(num_bars):
            # Calculate dynamic height based on sample buffer, level, and wave oscillation
            idx = int((i / num_bars) * len(self.recent_samples))
            sample_val = self.recent_samples[idx] if idx < len(self.recent_samples) else 0.0
            
            wave_mod = 0.5 + 0.5 * math.sin(self.phase + (i * 0.25))
            bar_height = max(3.0, (sample_val * 0.8 + self.level * 0.5) * max_bar_h * wave_mod)

            x = 12 + i * bar_spacing
            top_y = mid_y - bar_height
            bot_y = mid_y + bar_height

            # Color gradient: Cyan -> Emerald Green -> Orange/Red for loud peaks
            if self.level > 0.7:
                bar_color = QColor("#f43f5e")  # red
            elif self.level > 0.4:
                bar_color = QColor("#38bdf8")  # cyan
            else:
                bar_color = QColor("#10b981")  # emerald green

            painter.setPen(QPen(bar_color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(x), int(top_y), int(x), int(bot_y))

        # Centerline pulse
        painter.setPen(QPen(QColor(56, 189, 248, 80), 1))
        painter.drawLine(10, int(mid_y), w - 10, int(mid_y))

        # Live Recording Pulsing Badge in top left
        pulse_alpha = int(180 + 75 * math.sin(self.phase * 2))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(239, 68, 68, pulse_alpha))
        painter.drawEllipse(12, 10, 8, 8)

        painter.setPen(QColor("#f87171"))
        font = QFont("sans-serif", 9, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(26, 18, "LIVE RECORDING")
