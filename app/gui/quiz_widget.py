from typing import List, Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt

class QuizWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.questions: List[Dict[str, Any]] = []
        self.current_index = 0
        self.score = 0
        self.answered = False

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Header: Progress and Score
        header = QHBoxLayout()
        self.progress_lbl = QLabel("Question 0 of 0")
        self.progress_lbl.setStyleSheet("font-weight: bold; color: #60a5fa;")
        header.addWidget(self.progress_lbl)

        header.addStretch()

        self.score_lbl = QLabel("Score: 0 / 0")
        self.score_lbl.setStyleSheet("color: #34d399; font-weight: bold;")
        header.addWidget(self.score_lbl)
        layout.addLayout(header)

        # Question Frame
        self.q_frame = QFrame()
        self.q_frame.setStyleSheet("background-color: #1e293b; border-radius: 10px; padding: 18px; border: 1px solid #334155;")
        q_layout = QVBoxLayout(self.q_frame)
        q_layout.setSpacing(12)

        self.q_text = QLabel("No quiz questions loaded. Record audio to generate an interactive quiz!")
        self.q_text.setWordWrap(True)
        self.q_text.setStyleSheet("font-size: 16px; font-weight: 600; color: #f8fafc;")
        q_layout.addWidget(self.q_text)

        # Option Buttons Group
        self.btn_group = QButtonGroup(self)
        self.option_buttons = []
        self.options_container = QVBoxLayout()
        self.options_container.setSpacing(8)

        for i in range(4):
            btn = QPushButton(f"Option {i + 1}")
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0f172a;
                    color: #e2e8f0;
                    text-align: left;
                    padding: 10px 14px;
                    border-radius: 8px;
                    border: 1px solid #334155;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #1e3a8a;
                    border-color: #3b82f6;
                }
                QPushButton:checked {
                    background-color: #1d4ed8;
                    border-color: #60a5fa;
                    color: #ffffff;
                }
            """)
            self.btn_group.addButton(btn, i)
            self.option_buttons.append(btn)
            self.options_container.addWidget(btn)

        q_layout.addLayout(self.options_container)

        # Explanation box
        self.explanation_box = QFrame()
        self.explanation_box.setStyleSheet("background-color: #0f172a; border-left: 4px solid #10b981; border-radius: 6px; padding: 10px;")
        exp_layout = QVBoxLayout(self.explanation_box)
        self.exp_title = QLabel("Explanation")
        self.exp_title.setStyleSheet("font-weight: bold; color: #34d399; font-size: 12px;")
        exp_layout.addWidget(self.exp_title)
        self.exp_text = QLabel("")
        self.exp_text.setWordWrap(True)
        self.exp_text.setStyleSheet("color: #cbd5e1; font-size: 13px;")
        exp_layout.addWidget(self.exp_text)
        self.explanation_box.hide()
        q_layout.addWidget(self.explanation_box)

        layout.addWidget(self.q_frame, 1)

        # Action Buttons
        actions = QHBoxLayout()
        self.submit_btn = QPushButton("Submit Answer")
        self.submit_btn.setStyleSheet("background-color: #2563eb; color: #ffffff; font-weight: bold; padding: 10px 18px; border-radius: 8px; border: none;")
        self.submit_btn.clicked.connect(self.check_answer)
        actions.addWidget(self.submit_btn)

        self.next_q_btn = QPushButton("Next Question →")
        self.next_q_btn.setProperty("class", "secondaryBtn")
        self.next_q_btn.clicked.connect(self.next_question)
        self.next_q_btn.hide()
        actions.addWidget(self.next_q_btn)

        actions.addStretch()

        self.reset_btn = QPushButton("Restart Quiz")
        self.reset_btn.setProperty("class", "secondaryBtn")
        self.reset_btn.clicked.connect(self.restart_quiz)
        actions.addWidget(self.reset_btn)

        layout.addLayout(actions)

    def load_quiz(self, questions: List[Dict[str, Any]]):
        self.questions = questions or []
        self.restart_quiz()

    def restart_quiz(self):
        self.current_index = 0
        self.score = 0
        self.answered = False
        self.display_current_question()

    def display_current_question(self):
        self.answered = False
        self.explanation_box.hide()
        self.submit_btn.show()
        self.submit_btn.setEnabled(True)
        self.next_q_btn.hide()

        # Reset button styles and selection
        self.btn_group.setExclusive(False)
        for btn in self.option_buttons:
            btn.setChecked(False)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0f172a;
                    color: #e2e8f0;
                    text-align: left;
                    padding: 10px 14px;
                    border-radius: 8px;
                    border: 1px solid #334155;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #1e3a8a;
                    border-color: #3b82f6;
                }
                QPushButton:checked {
                    background-color: #1d4ed8;
                    border-color: #60a5fa;
                    color: #ffffff;
                }
            """)
        self.btn_group.setExclusive(True)

        if not self.questions:
            self.progress_lbl.setText("No questions loaded")
            self.q_text.setText("Record a meeting or lecture to generate knowledge check questions.")
            for btn in self.option_buttons:
                btn.hide()
            self.submit_btn.setEnabled(False)
            return

        total = len(self.questions)
        self.progress_lbl.setText(f"Question {self.current_index + 1} of {total}")
        self.score_lbl.setText(f"Score: {self.score} / {total}")

        q_data = self.questions[self.current_index]
        self.q_text.setText(q_data.get("question", ""))

        options = q_data.get("options", [])
        for i, btn in enumerate(self.option_buttons):
            if i < len(options):
                btn.setText(options[i])
                btn.show()
            else:
                btn.hide()

    def check_answer(self):
        selected_id = self.btn_group.checkedId()
        if selected_id == -1:
            return  # Nothing selected

        self.answered = True
        self.submit_btn.hide()
        self.next_q_btn.show()

        q_data = self.questions[self.current_index]
        correct_idx = q_data.get("correct_index", 0)

        if selected_id == correct_idx:
            self.score += 1
            # Highlight selected as green
            self.option_buttons[selected_id].setStyleSheet("background-color: #065f46; color: #ffffff; border: 2px solid #10b981; padding: 10px 14px; border-radius: 8px; text-align: left;")
            self.exp_title.setText("✓ Correct!")
            self.exp_title.setStyleSheet("color: #34d399; font-weight: bold;")
        else:
            # Highlight selected as red, correct as green
            self.option_buttons[selected_id].setStyleSheet("background-color: #7f1d1d; color: #ffffff; border: 2px solid #ef4444; padding: 10px 14px; border-radius: 8px; text-align: left;")
            if 0 <= correct_idx < len(self.option_buttons):
                self.option_buttons[correct_idx].setStyleSheet("background-color: #065f46; color: #ffffff; border: 2px solid #10b981; padding: 10px 14px; border-radius: 8px; text-align: left;")
            self.exp_title.setText("✗ Incorrect")
            self.exp_title.setStyleSheet("color: #f87171; font-weight: bold;")

        self.exp_text.setText(q_data.get("explanation", "Good job reviewing!"))
        self.explanation_box.show()
        self.score_lbl.setText(f"Score: {self.score} / {len(self.questions)}")

    def next_question(self):
        if self.current_index < len(self.questions) - 1:
            self.current_index += 1
            self.display_current_question()
        else:
            total = len(self.questions)
            pct = int((self.score / total) * 100) if total > 0 else 0
            self.q_text.setText(f"🎉 Quiz Completed! You scored {self.score} out of {total} ({pct}%).")
            for btn in self.option_buttons:
                btn.hide()
            self.explanation_box.hide()
            self.submit_btn.hide()
            self.next_q_btn.hide()
