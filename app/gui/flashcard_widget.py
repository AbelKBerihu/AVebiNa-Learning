from typing import List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt

class FlashcardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.flashcards: List[Dict[str, str]] = []
        self.current_index = 0
        self.showing_answer = False
        self.known_cards = set()

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Top Bar: Progress and Count
        top_bar = QHBoxLayout()
        self.counter_lbl = QLabel("No flashcards loaded")
        self.counter_lbl.setStyleSheet("font-weight: bold; color: #93c5fd;")
        top_bar.addWidget(self.counter_lbl)

        top_bar.addStretch()

        self.mastery_lbl = QLabel("Mastered: 0")
        self.mastery_lbl.setStyleSheet("color: #10b981; font-size: 13px; font-weight: 600;")
        top_bar.addWidget(self.mastery_lbl)
        layout.addLayout(top_bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background: #374151; border-radius: 3px; border: none; }
            QProgressBar::chunk { background: #3b82f6; border-radius: 3px; }
        """)
        layout.addWidget(self.progress_bar)

        # Card Display Frame
        self.card_frame = QFrame()
        self.card_frame.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 2px solid #3b82f6;
                border-radius: 12px;
                padding: 24px;
            }
        """)
        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        self.card_type_tag = QLabel("QUESTION")
        self.card_type_tag.setStyleSheet("color: #60a5fa; font-weight: bold; font-size: 12px;")
        card_layout.addWidget(self.card_type_tag)

        self.card_text = QLabel("Record a meeting or lecture to generate active-recall flashcards.")
        self.card_text.setWordWrap(True)
        self.card_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_text.setStyleSheet("font-size: 17px; line-height: 1.5; color: #f8fafc;")
        card_layout.addWidget(self.card_text, 1)

        self.flip_btn = QPushButton("Flip Card (Show Answer)")
        self.flip_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
                padding: 10px 18px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.flip_btn.clicked.connect(self.toggle_flip)
        card_layout.addWidget(self.flip_btn)

        layout.addWidget(self.card_frame, 1)

        # Navigation Controls
        nav_bar = QHBoxLayout()
        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.setProperty("class", "secondaryBtn")
        self.prev_btn.clicked.connect(self.prev_card)
        nav_bar.addWidget(self.prev_btn)

        self.mark_btn = QPushButton("✓ Mark as Mastered")
        self.mark_btn.setStyleSheet("background-color: #065f46; color: #34d399; font-weight: bold; padding: 8px 14px; border-radius: 8px; border: none;")
        self.mark_btn.clicked.connect(self.toggle_mastered)
        nav_bar.addWidget(self.mark_btn)

        self.next_btn = QPushButton("Next →")
        self.next_btn.setProperty("class", "secondaryBtn")
        self.next_btn.clicked.connect(self.next_card)
        nav_bar.addWidget(self.next_btn)

        layout.addLayout(nav_bar)

    def load_cards(self, cards: List[Dict[str, str]]):
        self.flashcards = cards or []
        self.current_index = 0
        self.showing_answer = False
        self.known_cards = set()
        self.update_card()

    def update_card(self):
        if not self.flashcards:
            self.counter_lbl.setText("No flashcards available")
            self.card_text.setText("Record or import audio to generate study flashcards.")
            self.card_type_tag.setText("")
            self.flip_btn.setEnabled(False)
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            self.mark_btn.setEnabled(False)
            self.progress_bar.setValue(0)
            return

        total = len(self.flashcards)
        self.flip_btn.setEnabled(True)
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < total - 1)
        self.mark_btn.setEnabled(True)

        self.counter_lbl.setText(f"Card {self.current_index + 1} of {total}")
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(len(self.known_cards))
        self.mastery_lbl.setText(f"Mastered: {len(self.known_cards)} / {total}")

        current = self.flashcards[self.current_index]

        if self.showing_answer:
            self.card_type_tag.setText("ANSWER")
            self.card_type_tag.setStyleSheet("color: #34d399; font-weight: bold; font-size: 12px;")
            self.card_text.setText(current.get("answer", ""))
            self.flip_btn.setText("Flip Back to Question")
        else:
            self.card_type_tag.setText("QUESTION")
            self.card_type_tag.setStyleSheet("color: #60a5fa; font-weight: bold; font-size: 12px;")
            self.card_text.setText(current.get("question", ""))
            self.flip_btn.setText("Flip Card (Show Answer)")

        if self.current_index in self.known_cards:
            self.mark_btn.setText("✓ Mastered")
            self.mark_btn.setStyleSheet("background-color: #064e3b; color: #6ee7b7; font-weight: bold; padding: 8px 14px; border-radius: 8px; border: none;")
        else:
            self.mark_btn.setText("Mark as Mastered")
            self.mark_btn.setStyleSheet("background-color: #374151; color: #9ca3af; font-weight: bold; padding: 8px 14px; border-radius: 8px; border: none;")

    def toggle_flip(self):
        self.showing_answer = not self.showing_answer
        self.update_card()

    def prev_card(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.showing_answer = False
            self.update_card()

    def next_card(self):
        if self.current_index < len(self.flashcards) - 1:
            self.current_index += 1
            self.showing_answer = False
            self.update_card()

    def toggle_mastered(self):
        if self.current_index in self.known_cards:
            self.known_cards.remove(self.current_index)
        else:
            self.known_cards.add(self.current_index)
        self.update_card()
