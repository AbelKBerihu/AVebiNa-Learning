from typing import List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt

class PodcastWidget(QWidget):
    """
    Google NotebookLM 'Deep Dive' Audio Overview.
    Displays an engaging, two-host conversational podcast breakdown
    of the recorded meeting or lecture.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dialogue: List[Dict[str, str]] = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Card
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e1b4b, stop:1 #312e81);
                border-radius: 10px;
                padding: 16px;
                border: 1px solid #4338ca;
            }
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(12, 8, 12, 8)

        v_text = QVBoxLayout()
        title = QLabel("🎙 NotebookLM Deep Dive — Two-Host Audio Overview")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #a5b4fc;")
        v_text.addWidget(title)

        desc = QLabel("Two AI hosts (Jordan & Taylor) banter, analyze, and break down this meeting/lecture into an engaging conversational discussion.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #cbd5e1; font-size: 13px;")
        v_text.addWidget(desc)
        h_layout.addLayout(v_text, 1)

        layout.addWidget(header_card)

        # Scroll Area for Podcast Conversation Turns
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setSpacing(12)
        self.chat_layout.addStretch()

        self.scroll.setWidget(self.chat_container)
        layout.addWidget(self.scroll, 1)

    def load_podcast(self, dialogue: List[Dict[str, str]]):
        self.dialogue = dialogue or []

        # Clear existing
        while self.chat_layout.count() > 1:
            child = self.chat_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self.dialogue:
            empty_lbl = QLabel("Record a meeting or lecture to generate an AI Deep Dive podcast discussion.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet("color: #64748b; font-size: 14px; padding: 30px;")
            self.chat_layout.insertWidget(0, empty_lbl)
            return

        for turn in self.dialogue:
            speaker = turn.get("speaker", "Host").strip()
            text = turn.get("text", "").strip()

            is_jordan = "jordan" in speaker.lower() or "host a" in speaker.lower()

            turn_box = QFrame()
            if is_jordan:
                turn_box.setStyleSheet("""
                    QFrame {
                        background-color: #1e293b;
                        border-left: 4px solid #38bdf8;
                        border-radius: 8px;
                        padding: 12px 16px;
                    }
                """)
                badge_color = "#38bdf8"
                avatar_tag = "🎙 Jordan"
            else:
                turn_box.setStyleSheet("""
                    QFrame {
                        background-color: #1a2234;
                        border-left: 4px solid #a855f7;
                        border-radius: 8px;
                        padding: 12px 16px;
                    }
                """)
                badge_color = "#c084fc"
                avatar_tag = "🎧 Taylor"

            box_layout = QVBoxLayout(turn_box)
            box_layout.setSpacing(6)
            box_layout.setContentsMargins(8, 4, 8, 4)

            spk_lbl = QLabel(avatar_tag)
            spk_lbl.setStyleSheet(f"font-weight: bold; color: {badge_color}; font-size: 13px;")
            box_layout.addWidget(spk_lbl)

            txt_lbl = QLabel(text)
            txt_lbl.setWordWrap(True)
            txt_lbl.setStyleSheet("color: #f1f5f9; font-size: 14px; line-height: 1.5;")
            box_layout.addWidget(txt_lbl)

            self.chat_layout.insertWidget(self.chat_layout.count() - 1, turn_box)
