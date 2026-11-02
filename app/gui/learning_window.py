import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

import markdown
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QTextEdit, QTextBrowser,
    QTabWidget, QFileDialog, QMessageBox, QFrame, QProgressBar,
    QCheckBox, QScrollArea, QSplitter, QSlider, QInputDialog, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal

from app.audio.recorder import AudioRecorder
from app.audio.player import AudioPlayer
from app.audio.ai_processor import LearningProcessor
from app.gui.waveform_widget import WaveformWidget
from app.gui.podcast_widget import PodcastWidget
from app.gui.flashcard_widget import FlashcardWidget
from app.gui.quiz_widget import QuizWidget
from app.gui.theme import DARK_THEME, get_markdown_css
from app.models import Item
from app.storage import Storage
from app.sync_engine import SyncEngine
from app.config import (
    get_db_path, get_recordings_dir, open_folder_in_file_manager,
    load_settings, save_settings
)

class AudioProcessWorker(QThread):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, processor: LearningProcessor, audio_path: str, topic_hint: str):
        super().__init__()
        self.processor = processor
        self.audio_path = audio_path
        self.topic_hint = topic_hint

    def run(self):
        try:
            result = self.processor.process_audio_file(self.audio_path, self.topic_hint)
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))

class VideoProcessWorker(QThread):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, processor: LearningProcessor, target: str, is_url: bool, topic_hint: str):
        super().__init__()
        self.processor = processor
        self.target = target
        self.is_url = is_url
        self.topic_hint = topic_hint

    def run(self):
        try:
            if self.is_url:
                result = self.processor.process_youtube_url(self.target, self.topic_hint)
            else:
                result = self.processor.process_video_file(self.target, self.topic_hint)
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))

class TutorWorker(QThread):
    answered = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, processor: LearningProcessor, context: str, question: str):
        super().__init__()
        self.processor = processor
        self.context = context
        self.question = question

    def run(self):
        try:
            ans = self.processor.ask_grounded_tutor(self.context, self.question)
            self.answered.emit(ans)
        except Exception as e:
            self.failed.emit(str(e))

class LearningWindow(QMainWindow):
    def __init__(self, storage: Optional[Storage] = None):
        super().__init__()
        self.storage = storage or Storage(get_db_path())
        self.settings = load_settings()

        self.setWindowTitle("AVebiNa Learning — Live Meeting AI Companion & NotebookLM Studio")
        self.resize(1280, 880)
        self.setStyleSheet(DARK_THEME)

        self.recorder = AudioRecorder(on_level_update=self.on_audio_data_update)
        self.player = AudioPlayer(
            on_progress=self.on_playback_progress,
            on_finished=self.on_playback_finished
        )
        self.processor = LearningProcessor(
            gemini_api_key=self.settings.get("gemini_api_key", os.environ.get("GEMINI_API_KEY", "")),
            openai_api_key=self.settings.get("openai_api_key", os.environ.get("OPENAI_API_KEY", "")),
            ollama_endpoint=self.settings.get("ollama_endpoint", "http://localhost:11434")
        )

        self.sync_engine = SyncEngine(
            storage=self.storage,
            server_url=self.settings.get("server_url", "http://127.0.0.1:8765"),
            sync_token=self.settings.get("sync_token", "cross-sync-secret-key")
        )

        self.recorded_audio_path: Optional[str] = None
        self.current_learning_data: Dict[str, Any] = {}
        self.notebook_sources: List[Dict[str, str]] = []
        self.record_seconds = 0
        self.worker: Optional[QThread] = None

        # Timer for recording clock
        self.record_timer = QTimer(self)
        self.record_timer.setInterval(1000)
        self.record_timer.timeout.connect(self.update_record_timer)

        self.init_ui()
        self.refresh_audio_devices()
        self.update_ai_banner()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # 1. AI API Status & Storage Banner
        top_info_banner = self._create_ai_status_banner()
        main_layout.addWidget(top_info_banner)

        # 2. Top Audio Capture & Waveform Visualizer Toolbar
        top_frame = self._create_audio_toolbar()
        main_layout.addWidget(top_frame)

        # 3. Audio Playback Control Strip
        self.playback_frame = self._create_playback_strip()
        main_layout.addWidget(self.playback_frame)

        # 4. Main Notebook Splitter (NotebookLM Left Sources Drawer + Right Learning Workspace)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Left: Notebook Sources Drawer
        sources_pane = self._create_sources_pane()
        splitter.addWidget(sources_pane)

        # Right: Notebook Workspace Tabs
        workspace_pane = self._create_workspace_pane()
        splitter.addWidget(workspace_pane)

        splitter.setSizes([260, 980])
        main_layout.addWidget(splitter, 1)

    # ------------------ AI STATUS BANNER ------------------
    def _create_ai_status_banner(self) -> QFrame:
        banner = QFrame()
        banner.setStyleSheet("background-color: #0f172a; border-radius: 8px; padding: 6px 14px; border: 1px solid #1e293b;")
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(4, 2, 4, 2)

        self.ai_status_lbl = QLabel("")
        layout.addWidget(self.ai_status_lbl)

        layout.addStretch()

        self.storage_path_lbl = QLabel(f"📂 Storage: {get_recordings_dir()}")
        self.storage_path_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(self.storage_path_lbl)

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.setProperty("class", "secondaryBtn")
        open_folder_btn.setStyleSheet("padding: 3px 10px; font-size: 11px;")
        open_folder_btn.clicked.connect(lambda: open_folder_in_file_manager(get_recordings_dir()))
        layout.addWidget(open_folder_btn)

        self.config_ai_btn = QPushButton("🔑 Configure AI Key")
        self.config_ai_btn.setProperty("class", "secondaryBtn")
        self.config_ai_btn.setStyleSheet("padding: 3px 10px; font-size: 11px;")
        self.config_ai_btn.clicked.connect(self.open_api_settings)
        layout.addWidget(self.config_ai_btn)

        return banner

    def update_ai_banner(self):
        status = self.processor.get_active_provider_status()
        if status["connected"]:
            self.ai_status_lbl.setText(f"✓ AI Active: {status['name']}")
            self.ai_status_lbl.setStyleSheet("color: #34d399; font-weight: bold; font-size: 12px;")
            self.config_ai_btn.setText("⚙ AI Settings")
        else:
            self.ai_status_lbl.setText("⚠️ Free Gemini API Key required for live summarization")
            self.ai_status_lbl.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 12px;")
            self.config_ai_btn.setText("🔑 Enter Free API Key")

    # ------------------ AUDIO CAPTURE & WAVEFORM TOOLBAR ------------------
    def _create_audio_toolbar(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("background-color: #1f2937; border-radius: 12px; padding: 12px; border: 1px solid #374151;")
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)

        row1 = QHBoxLayout()
        row1.setSpacing(10)

        # Device selector
        row1.addWidget(QLabel("Source:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(260)
        row1.addWidget(self.device_combo)

        refresh_dev_btn = QPushButton("🔄")
        refresh_dev_btn.setStyleSheet("padding: 6px 10px; background: #374151; color: white; border-radius: 6px; border: none;")
        refresh_dev_btn.clicked.connect(self.refresh_audio_devices)
        row1.addWidget(refresh_dev_btn)

        self.mix_mic_check = QCheckBox("Mix in Mic")
        self.mix_mic_check.setToolTip("Records both Google Meet participants and your own microphone simultaneously")
        self.mix_mic_check.setChecked(True)
        row1.addWidget(self.mix_mic_check)

        row1.addSpacing(10)

        # Live Recording Button
        self.record_btn = QPushButton("⏺ Start Listening / Record")
        self.record_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                font-weight: bold;
                padding: 10px 18px;
                border-radius: 8px;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover { background-color: #b91c1c; }
        """)
        self.record_btn.clicked.connect(self.toggle_recording)
        row1.addWidget(self.record_btn)

        self.timer_lbl = QLabel("00:00:00")
        self.timer_lbl.setStyleSheet("font-family: monospace; font-size: 18px; font-weight: bold; color: #f3f4f6; padding: 0 8px;")
        row1.addWidget(self.timer_lbl)

        # Real Live Waveform Oscilloscope Widget
        self.waveform_widget = WaveformWidget()
        row1.addWidget(self.waveform_widget, 1)

        layout.addLayout(row1)

        # Row 2: Topic & NotebookLM actions
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Session Topic:"))
        self.topic_input = QLineEdit()
        self.topic_input.setPlaceholderText("e.g. Google Meet: Biology 101 Lecture — Photosynthesis & Cellular Respiration")
        row2.addWidget(self.topic_input, 1)

        self.watch_video_btn = QPushButton("🎥 Watch Video / YouTube")
        self.watch_video_btn.setProperty("class", "secondaryBtn")
        self.watch_video_btn.clicked.connect(self.watch_and_summarize_video)
        row2.addWidget(self.watch_video_btn)

        import_btn = QPushButton("📁 Import Audio")
        import_btn.setProperty("class", "secondaryBtn")
        import_btn.clicked.connect(self.import_audio_file)
        row2.addWidget(import_btn)

        self.reprocess_btn = QPushButton("✨ Synthesize NotebookLM Study Guide")
        self.reprocess_btn.setStyleSheet("background-color: #2563eb; color: #ffffff; font-weight: bold; padding: 8px 16px; border-radius: 8px; border: none;")
        self.reprocess_btn.clicked.connect(self.trigger_ai_processing)
        self.reprocess_btn.setEnabled(False)
        row2.addWidget(self.reprocess_btn)

        layout.addLayout(row2)
        return frame

    # ------------------ PLAYBACK STRIP ------------------
    def _create_playback_strip(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("background-color: #111827; border-radius: 8px; padding: 6px 12px; border: 1px solid #1f2937;")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(10)

        play_title = QLabel("🎧 Audio Playback:")
        play_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #94a3b8;")
        layout.addWidget(play_title)

        self.play_pause_btn = QPushButton("▶ Play")
        self.play_pause_btn.setProperty("class", "secondaryBtn")
        self.play_pause_btn.setStyleSheet("padding: 4px 12px; font-size: 12px;")
        self.play_pause_btn.clicked.connect(self.toggle_playback)
        self.play_pause_btn.setEnabled(False)
        layout.addWidget(self.play_pause_btn)

        self.stop_play_btn = QPushButton("⏹")
        self.stop_play_btn.setProperty("class", "secondaryBtn")
        self.stop_play_btn.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        self.stop_play_btn.clicked.connect(self.stop_playback)
        self.stop_play_btn.setEnabled(False)
        layout.addWidget(self.stop_play_btn)

        self.play_slider = QSlider(Qt.Orientation.Horizontal)
        self.play_slider.setRange(0, 1000)
        self.play_slider.sliderMoved.connect(self.on_slider_moved)
        self.play_slider.setEnabled(False)
        layout.addWidget(self.play_slider, 1)

        self.playback_time_lbl = QLabel("00:00 / 00:00")
        self.playback_time_lbl.setStyleSheet("font-family: monospace; font-size: 12px; color: #94a3b8;")
        layout.addWidget(self.playback_time_lbl)

        return frame

    # ------------------ NOTEBOOKLM SOURCES DRAWER ------------------
    def _create_sources_pane(self) -> QWidget:
        pane = QFrame()
        pane.setStyleSheet("background-color: #111827; border-right: 1px solid #374151; padding: 6px;")
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(6, 10, 6, 10)
        layout.setSpacing(8)

        lbl = QLabel("NOTEBOOK SOURCES")
        lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #60a5fa; padding: 4px;")
        layout.addWidget(lbl)

        self.sources_list = QListWidget()
        self.sources_list.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.sources_list, 1)

        add_doc_btn = QPushButton("+ Add Document (.pdf/.txt)")
        add_doc_btn.setProperty("class", "secondaryBtn")
        add_doc_btn.setStyleSheet("font-size: 12px; padding: 6px;")
        add_doc_btn.clicked.connect(self.import_document_file)
        layout.addWidget(add_doc_btn)

        return pane

    # ------------------ WORKSPACE TABS ------------------
    def _create_workspace_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(8)

        # Action Strip
        action_strip = QHBoxLayout()
        self.status_label = QLabel("Ready. Audio waveform visualizer is active.")
        self.status_label.setStyleSheet("color: #94a3b8; font-weight: 500;")
        action_strip.addWidget(self.status_label)
        action_strip.addStretch()

        self.save_sync_btn = QPushButton("☁ Save & Sync to CrossSync")
        self.save_sync_btn.setStyleSheet("background-color: #065f46; color: #34d399; font-weight: bold; padding: 6px 14px; border-radius: 6px; border: none;")
        self.save_sync_btn.clicked.connect(self.save_and_sync_all)
        self.save_sync_btn.setEnabled(False)
        action_strip.addWidget(self.save_sync_btn)

        self.export_anki_btn = QPushButton("Anki Flashcards (.txt)")
        self.export_anki_btn.setProperty("class", "secondaryBtn")
        self.export_anki_btn.setStyleSheet("padding: 6px 12px; font-size: 13px;")
        self.export_anki_btn.clicked.connect(self.export_anki_flashcards)
        self.export_anki_btn.setEnabled(False)
        action_strip.addWidget(self.export_anki_btn)

        self.export_html_btn = QPushButton("Print Study Guide (.html)")
        self.export_html_btn.setProperty("class", "secondaryBtn")
        self.export_html_btn.setStyleSheet("padding: 6px 12px; font-size: 13px;")
        self.export_html_btn.clicked.connect(self.export_html_study_guide)
        self.export_html_btn.setEnabled(False)
        action_strip.addWidget(self.export_html_btn)

        self.export_md_btn = QPushButton("Markdown")
        self.export_md_btn.setProperty("class", "secondaryBtn")
        self.export_md_btn.setStyleSheet("padding: 6px 12px; font-size: 13px;")
        self.export_md_btn.clicked.connect(self.export_markdown)
        self.export_md_btn.setEnabled(False)
        action_strip.addWidget(self.export_md_btn)

        layout.addLayout(action_strip)

        # Tabs
        self.tabs = QTabWidget()

        # Tab 1: Study Notes & Executive Summary
        self.notes_browser = QTextBrowser()
        self.notes_browser.setObjectName("previewBrowser")
        self.notes_browser.setHtml(
            f"<style>{get_markdown_css()}</style>"
            "<h2>Welcome to AVebiNa Learning & NotebookLM Studio</h2>"
            "<p>Capture any lecture or Google Meeting live, or import video files to watch and summarize.</p>"
            "<ul>"
            "<li><b>Live Waveform:</b> The animated wave bar shows live vocal speech frequencies in real time.</li>"
            "<li><b>Google Meet Audio:</b> Select <i>[System / Meeting Audio]</i> to capture participant audio directly.</li>"
            "<li><b>NotebookLM Two-Host Podcast:</b> Generates engaging conversational Audio Overview dialogues.</li>"
            "<li><b>Watch & Summarize:</b> Processes video files (.mp4) and YouTube links.</li>"
            "</ul>"
        )
        self.tabs.addTab(self.notes_browser, "📝 Study Notes & Summary")

        # Tab 2: NotebookLM Two-Host Deep Dive Podcast
        self.podcast_widget = PodcastWidget()
        self.tabs.addTab(self.podcast_widget, "🎙 Deep Dive Podcast (Audio Overview)")

        # Tab 3: Interactive Flashcards
        self.flashcard_widget = FlashcardWidget()
        self.tabs.addTab(self.flashcard_widget, "📇 Flashcards (Active Recall)")

        # Tab 4: Knowledge Check Quiz
        self.quiz_widget = QuizWidget()
        self.tabs.addTab(self.quiz_widget, "❓ Quiz & Knowledge Check")

        # Tab 5: Action Items & Homework
        self.tasks_tab = self._create_tasks_tab()
        self.tabs.addTab(self.tasks_tab, "📋 Action Items & Homework")

        # Tab 6: Verbatim Transcript
        self.transcript_browser = QTextBrowser()
        self.transcript_browser.setObjectName("previewBrowser")
        self.transcript_browser.setPlaceholderText("Verbatim transcript with timestamps will appear here after recording...")
        self.tabs.addTab(self.transcript_browser, "📜 Full Transcript")

        # Tab 7: Grounded NotebookLM Chat
        self.tutor_tab = self._create_tutor_tab()
        self.tabs.addTab(self.tutor_tab, "💬 Grounded NotebookLM Chat")

        layout.addWidget(self.tabs, 1)
        return pane

    def _create_tasks_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)

        self.tasks_container = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setSpacing(8)
        self.tasks_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setWidget(self.tasks_container)

        layout.addWidget(scroll)
        return widget

    def _create_tutor_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.tutor_history = QTextBrowser()
        self.tutor_history.setObjectName("previewBrowser")
        self.tutor_history.setHtml(
            f"<style>{get_markdown_css()}</style>"
            "<p><b>NotebookLM Grounded Chat ready!</b> Ask any question about your recorded meeting, video, or lecture sources. Responses include citations.</p>"
        )
        layout.addWidget(self.tutor_history, 1)

        input_row = QHBoxLayout()
        self.tutor_input = QLineEdit()
        self.tutor_input.setPlaceholderText("Ask a question about your sources... (e.g. 'What was discussed in minute 14?')")
        self.tutor_input.returnPressed.connect(self.ask_tutor)
        input_row.addWidget(self.tutor_input, 1)

        send_btn = QPushButton("Ask Sources")
        send_btn.setProperty("class", "primaryBtn")
        send_btn.clicked.connect(self.ask_tutor)
        input_row.addWidget(send_btn)

        layout.addLayout(input_row)
        return widget

    # ------------------ AUDIO CAPTURE & WAVEFORM ------------------
    def refresh_audio_devices(self):
        self.device_combo.clear()
        devices = self.recorder.get_audio_devices()

        default_idx = 0
        for i, dev in enumerate(devices):
            self.device_combo.addItem(dev["display_name"], dev["id"])
            if dev.get("is_loopback"):
                default_idx = i
            elif dev.get("is_default") and default_idx == 0:
                default_idx = i

        if devices:
            self.device_combo.setCurrentIndex(default_idx)

    def on_audio_data_update(self, level: float, chunk: Optional[Any] = None):
        self.waveform_widget.update_audio_data(level, chunk)

    def update_record_timer(self):
        self.record_seconds += 1
        mins = self.record_seconds // 60
        secs = self.record_seconds % 60
        hours = mins // 60
        mins = mins % 60
        self.timer_lbl.setText(f"{hours:02d}:{mins:02d}:{secs:02d}")

    def toggle_recording(self):
        if not self.recorder.is_recording:
            # START RECORDING
            dev_id = self.device_combo.currentData()
            sec_dev_id = None
            if self.mix_mic_check.isChecked():
                devices = self.recorder.get_audio_devices()
                mic_dev = next((d for d in devices if not d.get("is_loopback")), None)
                if mic_dev and mic_dev["id"] != dev_id:
                    sec_dev_id = mic_dev["id"]

            try:
                self.recorder.start_recording(device_id=dev_id, secondary_device_id=sec_dev_id)
            except Exception as e:
                QMessageBox.critical(self, "Audio Error", f"Could not start recording: {e}")
                return

            self.record_seconds = 0
            self.timer_lbl.setText("00:00:00")
            self.record_timer.start()
            self.waveform_widget.set_recording_state(True)

            self.record_btn.setText("⏹ Stop & Analyze")
            self.record_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e11d48;
                    color: #ffffff;
                    font-weight: bold;
                    padding: 10px 18px;
                    border-radius: 8px;
                    font-size: 14px;
                    border: 2px solid #fda4af;
                }
            """)
            self.status_label.setText("🎙 Live recording active. Dynamic waveform visualizer is bouncing with speech.")
            self.status_label.setStyleSheet("color: #f43f5e; font-weight: bold;")
            self.device_combo.setEnabled(False)
            self.reprocess_btn.setEnabled(False)
        else:
            # STOP RECORDING
            self.record_timer.stop()
            self.waveform_widget.set_recording_state(False)
            self.status_label.setText("Saving audio recording to disk...")

            # Save in designated recordings directory
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"session_{timestamp}.wav"
            target_path = str(get_recordings_dir() / filename)

            saved_path = self.recorder.stop_recording(output_filepath=target_path)
            self.recorded_audio_path = saved_path

            self.record_btn.setText("⏺ Start Listening / Record")
            self.record_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc2626;
                    color: #ffffff;
                    font-weight: bold;
                    padding: 10px 18px;
                    border-radius: 8px;
                    font-size: 14px;
                    border: none;
                }
                QPushButton:hover { background-color: #b91c1c; }
            """)
            self.device_combo.setEnabled(True)
            self.reprocess_btn.setEnabled(True)

            if saved_path:
                self.add_source_to_drawer("🎙 Live Meeting Audio", Path(saved_path).name, saved_path)
                self.status_label.setText(f"Saved: {Path(saved_path).name}. Synthesizing NotebookLM study guide...")
                self.load_audio_into_player(saved_path)
                self.trigger_ai_processing()
            else:
                self.status_label.setText("No audio was recorded.")

    def add_source_to_drawer(self, source_type: str, name: str, path: str):
        self.notebook_sources.append({"type": source_type, "name": name, "path": path})
        item = QListWidgetItem(f"{source_type}\n  {name}")
        self.sources_list.addItem(item)

    # ------------------ WATCH VIDEO & IMPORT ------------------
    def watch_and_summarize_video(self):
        """Allows user to either import a video file or enter a YouTube URL to watch & summarize."""
        choice, ok = QInputDialog.getItem(
            self,
            "Watch then Summarize",
            "Choose Video Source:",
            ["1. Local Video File (.mp4, .webm, .mkv, .mov)", "2. YouTube / Meeting Video URL"],
            0,
            False
        )
        if not ok:
            return

        if "Local Video" in choice:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Video File to Watch & Summarize",
                "",
                "Video Files (*.mp4 *.webm *.mkv *.mov *.avi);;All Files (*)"
            )
            if file_path:
                self.recorded_audio_path = file_path
                self.add_source_to_drawer("🎥 Video File", Path(file_path).name, file_path)
                if not self.topic_input.text():
                    self.topic_input.setText(Path(file_path).stem.replace("_", " ").title())
                self.status_label.setText(f"Analyzing video: {Path(file_path).name}...")
                self.worker = VideoProcessWorker(self.processor, file_path, is_url=False, topic_hint=self.topic_input.text())
                self.worker.finished.connect(self.on_processing_finished)
                self.worker.failed.connect(self.on_processing_failed)
                self.worker.start()
        else:
            url, ok = QInputDialog.getText(self, "Watch YouTube / Meeting Video", "Enter Video URL:")
            if ok and url.strip():
                url = url.strip()
                self.add_source_to_drawer("🌐 Web Video", url[:35] + "...", url)
                self.status_label.setText("Downloading audio stream & watching video...")
                self.worker = VideoProcessWorker(self.processor, url, is_url=True, topic_hint=self.topic_input.text())
                self.worker.finished.connect(self.on_processing_finished)
                self.worker.failed.connect(self.on_processing_failed)
                self.worker.start()

    def import_audio_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            "",
            "Audio Files (*.wav *.mp3 *.m4a *.ogg *.flac *.webm);;All Files (*)"
        )
        if file_path:
            self.recorded_audio_path = file_path
            self.add_source_to_drawer("📁 Audio File", Path(file_path).name, file_path)
            if not self.topic_input.text():
                self.topic_input.setText(Path(file_path).stem.replace("_", " ").title())
            self.load_audio_into_player(file_path)
            self.trigger_ai_processing()

    def import_document_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Document to Add as Source",
            "",
            "Text & Markdown Files (*.txt *.md *.py *.json *.csv);;All Files (*)"
        )
        if file_path:
            self.add_source_to_drawer("📄 Document", Path(file_path).name, file_path)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                # Append to current notes context
                current_text = self.notes_browser.toPlainText()
                new_context = f"{current_text}\n\n# Document Source: {Path(file_path).name}\n\n{content}"
                styled_html = f"<style>{get_markdown_css()}</style>{markdown.markdown(new_context)}"
                self.notes_browser.setHtml(styled_html)
                QMessageBox.information(self, "Document Added", f"Added '{Path(file_path).name}' as a grounded source!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not read document: {e}")

    # ------------------ PLAYBACK LOGIC ------------------
    def load_audio_into_player(self, file_path: str):
        if file_path.lower().endswith(".wav"):
            if self.player.load_file(file_path):
                self.play_pause_btn.setEnabled(True)
                self.stop_play_btn.setEnabled(True)
                self.play_slider.setEnabled(True)
                mins = int(self.player.total_seconds) // 60
                secs = int(self.player.total_seconds) % 60
                self.playback_time_lbl.setText(f"00:00 / {mins:02d}:{secs:02d}")

    def toggle_playback(self):
        if self.player.is_playing:
            self.player.pause()
            self.play_pause_btn.setText("▶ Play")
        else:
            if self.player.play():
                self.play_pause_btn.setText("⏸ Pause")

    def stop_playback(self):
        self.player.stop()
        self.play_pause_btn.setText("▶ Play")
        self.play_slider.setValue(0)

    def on_playback_progress(self, current: float, total: float):
        if total > 0:
            val = int((current / total) * 1000)
            self.play_slider.blockSignals(True)
            self.play_slider.setValue(val)
            self.play_slider.blockSignals(False)

            cur_m, cur_s = int(current) // 60, int(current) % 60
            tot_m, tot_s = int(total) // 60, int(total) % 60
            self.playback_time_lbl.setText(f"{cur_m:02d}:{cur_s:02d} / {tot_m:02d}:{tot_s:02d}")

    def on_playback_finished(self):
        self.play_pause_btn.setText("▶ Play")
        self.play_slider.setValue(0)

    def on_slider_moved(self, value: int):
        target_sec = (value / 1000.0) * self.player.total_seconds
        self.player.seek(target_sec)

    # ------------------ AI PROCESSING ------------------
    def trigger_ai_processing(self):
        if not self.recorded_audio_path:
            QMessageBox.information(self, "No Source", "Please record or import an audio or video file first.")
            return

        topic = self.topic_input.text().strip()
        self.status_label.setText("🤖 Synthesizing NotebookLM Study Guide (Podcast, Notes, Flashcards)...")
        self.status_label.setStyleSheet("color: #38bdf8; font-weight: bold;")
        self.reprocess_btn.setEnabled(False)

        self.worker = AudioProcessWorker(self.processor, self.recorded_audio_path, topic)
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.failed.connect(self.on_processing_failed)
        self.worker.start()

    def on_processing_finished(self, data: dict):
        self.reprocess_btn.setEnabled(True)
        self.save_sync_btn.setEnabled(True)
        self.export_anki_btn.setEnabled(True)
        self.export_html_btn.setEnabled(True)
        self.export_md_btn.setEnabled(True)
        self.current_learning_data = data

        self.status_label.setText("✓ NotebookLM Study Package Synthesized Successfully!")
        self.status_label.setStyleSheet("color: #34d399; font-weight: bold;")

        title = data.get("title", "Lecture Study Guide")
        if not self.topic_input.text():
            self.topic_input.setText(title)

        # 1. Render Study Notes Tab
        summary = data.get("summary", "")
        study_notes = data.get("study_notes", "")
        full_md = f"# {title}\n\n## Executive Summary\n{summary}\n\n{study_notes}"
        html = markdown.markdown(full_md, extensions=['fenced_code', 'tables'])
        styled_html = f"<style>{get_markdown_css()}</style>{html}"
        self.notes_browser.setHtml(styled_html)

        # 2. Render NotebookLM Two-Host Podcast Tab
        podcast = data.get("deep_dive_podcast", [])
        self.podcast_widget.load_podcast(podcast)

        # 3. Render Flashcards
        flashcards = data.get("flashcards", [])
        self.flashcard_widget.load_cards(flashcards)

        # 4. Render Quiz
        quiz = data.get("quiz", [])
        self.quiz_widget.load_quiz(quiz)

        # 5. Render Action Items
        self._populate_tasks(data.get("action_items", []))

        # 6. Render Transcript
        transcript = data.get("transcript", "No transcript available.")
        self.transcript_browser.setPlainText(transcript)

    def on_processing_failed(self, error: str):
        self.reprocess_btn.setEnabled(True)
        self.status_label.setText(f"AI notice: {error}")
        self.status_label.setStyleSheet("color: #ef4444;")
        QMessageBox.warning(
            self,
            "AI Notice",
            f"Could not complete AI processing:\n\n{error}\n\n"
            "Please configure your Google Gemini API key in Settings (⚙) to enable live transcription."
        )

    def _populate_tasks(self, action_items: List[Dict[str, Any]]):
        while self.tasks_layout.count() > 1:
            item = self.tasks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not action_items:
            lbl = QLabel("No specific action items or homework were identified.")
            lbl.setStyleSheet("color: #94a3b8; font-style: italic; padding: 12px;")
            self.tasks_layout.insertWidget(0, lbl)
            return

        for item in action_items:
            task_box = QFrame()
            task_box.setStyleSheet("background: #1e293b; border-radius: 8px; padding: 10px; border: 1px solid #334155;")
            tb_layout = QHBoxLayout(task_box)
            tb_layout.setContentsMargins(8, 4, 8, 4)

            chk = QCheckBox(item.get("title", ""))
            chk.setChecked(item.get("completed", False))
            chk.setStyleSheet("font-size: 14px; font-weight: 500; color: #f1f5f9;")
            tb_layout.addWidget(chk, 1)

            due = item.get("due")
            if due:
                due_lbl = QLabel(f"Due: {due}")
                due_lbl.setStyleSheet("color: #f59e0b; font-size: 12px; font-weight: bold; padding: 2px 8px; background: #451a03; border-radius: 4px;")
                tb_layout.addWidget(due_lbl)

            self.tasks_layout.insertWidget(self.tasks_layout.count() - 1, task_box)

    # ------------------ NOTEBOOKLM GROUNDED CHAT ------------------
    def ask_tutor(self):
        question = self.tutor_input.text().strip()
        if not question:
            return

        context = self.current_learning_data.get("study_notes") or self.notes_browser.toPlainText()
        self.tutor_input.clear()

        user_block = f"<p style='color: #60a5fa;'><b>You:</b> {question}</p><p style='color: #94a3b8;'><i>NotebookLM is searching sources...</i></p>"
        self.tutor_history.append(user_block)

        self.worker = TutorWorker(self.processor, context, question)
        self.worker.answered.connect(self.on_tutor_answered)
        self.worker.failed.connect(lambda err: self.tutor_history.append(f"<p style='color: #ef4444;'>Error: {err}</p>"))
        self.worker.start()

    def on_tutor_answered(self, answer: str):
        html_ans = markdown.markdown(answer)
        block = f"<div style='background: #1e293b; border-left: 3px solid #3b82f6; padding: 10px; margin: 8px 0; border-radius: 6px;'><b>NotebookLM Grounded Response:</b>{html_ans}</div>"
        self.tutor_history.append(block)

    # ------------------ EXPORT & SYNC ------------------
    def save_and_sync_all(self):
        if not self.current_learning_data:
            return

        title = self.current_learning_data.get("title") or self.topic_input.text() or "Meeting Notes"
        summary = self.current_learning_data.get("summary", "")
        study_notes = self.current_learning_data.get("study_notes", "")
        transcript = self.current_learning_data.get("transcript", "")

        full_content = f"{summary}\n\n{study_notes}\n\n## Transcript Snippet\n{transcript[:1500]}"

        note_item = Item(
            item_type="note",
            title=title,
            content=full_content,
            tags="meeting, notebooklm, learning",
            is_pinned=True
        )
        self.storage.save_item(note_item, mark_dirty=True)

        for t in self.current_learning_data.get("action_items", []):
            task_title = t.get("title", "")
            if task_title:
                task_item = Item(
                    item_type="task",
                    title=task_title,
                    status="pending",
                    tags="homework, follow-up"
                )
                self.storage.save_item(task_item, mark_dirty=True)

        self.status_label.setText("Syncing notes & tasks to your devices...")
        ok, msg = self.sync_engine.perform_sync()

        if ok:
            QMessageBox.information(
                self,
                "Saved & Synchronized",
                f"✓ Successfully saved '{title}' and synchronized with your CrossSync devices!\n\n"
                f"You can review these notes on both your Windows and Linux machines."
            )
            self.status_label.setText("✓ Notes & Tasks synchronized across devices.")
        else:
            QMessageBox.information(
                self,
                "Saved Locally",
                f"✓ Successfully saved '{title}' to local storage!\n\n"
                f"Server status: {msg}. Changes will synchronize automatically as soon as the server is reachable."
            )
            self.status_label.setText("Saved locally (will auto-sync when online).")

    def export_anki_flashcards(self):
        flashcards = self.current_learning_data.get("flashcards", [])
        if not flashcards:
            QMessageBox.information(self, "No Flashcards", "No flashcards generated yet.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Anki Flashcards",
            f"{self.topic_input.text() or 'flashcards'}_anki.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("#separator:tab\n#html:true\n")
                for fc in flashcards:
                    q = fc.get("question", "").replace("\t", " ").replace("\n", "<br>")
                    a = fc.get("answer", "").replace("\t", " ").replace("\n", "<br>")
                    f.write(f"{q}\t{a}\n")
            QMessageBox.information(self, "Exported", f"Exported {len(flashcards)} flashcards for Anki to:\n{file_path}")

    def export_html_study_guide(self):
        if not self.current_learning_data:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Printable Study Guide",
            f"{self.topic_input.text() or 'study_guide'}.html",
            "HTML Files (*.html);;All Files (*)"
        )
        if file_path:
            title = self.current_learning_data.get("title", "Study Guide")
            summary = self.current_learning_data.get("summary", "")
            notes = self.current_learning_data.get("study_notes", "")
            podcast = self.current_learning_data.get("deep_dive_podcast", [])
            flashcards = self.current_learning_data.get("flashcards", [])
            quiz = self.current_learning_data.get("quiz", [])

            notes_html = markdown.markdown(f"## Summary\n{summary}\n\n{notes}")

            podcast_html = "".join([
                f"<div class='podcast-turn'><b>{t.get('speaker','')}:</b> {t.get('text','')}</div>"
                for t in podcast
            ])

            fc_html = "".join([
                f"<div class='card'><b>Q:</b> {fc.get('question','')}<br><b>A:</b> {fc.get('answer','')}</div>"
                for fc in flashcards
            ])

            quiz_html = "".join([
                f"<div class='quiz-q'><p><b>Q:</b> {q.get('question','')}</p>" +
                "".join([f"<div>• {opt}</div>" for opt in q.get("options",[])]) +
                f"<p class='ans'><i>Answer: {q.get('options',[])[q.get('correct_index',0)] if q.get('options') else ''} — {q.get('explanation','')}</i></p></div>"
                for q in quiz
            ])

            full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; max-width: 850px; margin: 40px auto; padding: 0 20px; color: #1e293b; }}
    h1 {{ color: #1e3a8a; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; }}
    h2 {{ color: #2563eb; margin-top: 24px; }}
    .podcast-turn {{ background: #f8fafc; border-left: 3px solid #6366f1; padding: 8px 12px; margin-bottom: 8px; }}
    .card {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; margin-bottom: 10px; }}
    .quiz-q {{ background: #f1f5f9; border-radius: 8px; padding: 14px; margin-bottom: 14px; }}
    .ans {{ color: #047857; margin-top: 8px; font-size: 13px; }}
</style>
</head>
<body>
    <h1>{title}</h1>
    {notes_html}
    <h2>NotebookLM Two-Host Deep Dive Conversation</h2>
    {podcast_html}
    <h2>Flashcards & Active Recall</h2>
    {fc_html}
    <h2>Knowledge Check Quiz & Solutions</h2>
    {quiz_html}
</body>
</html>"""
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full_html)
            QMessageBox.information(self, "Exported", f"Exported printable study guide to:\n{file_path}")

    def export_markdown(self):
        if not self.current_learning_data:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Study Notes",
            f"{self.topic_input.text() or 'lecture_notes'}.md",
            "Markdown Files (*.md);;All Files (*)"
        )
        if file_path:
            title = self.current_learning_data.get("title", "")
            summary = self.current_learning_data.get("summary", "")
            notes = self.current_learning_data.get("study_notes", "")
            full = f"# {title}\n\n## Summary\n{summary}\n\n{notes}"
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full)
            QMessageBox.information(self, "Exported", f"Successfully exported notes to:\n{file_path}")

    def open_api_settings(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout
        diag = QDialog(self)
        diag.setWindowTitle("AI & Gemini Settings")
        diag.setMinimumWidth(480)
        d_layout = QVBoxLayout(diag)
        
        info = QLabel(
            "<b>Connect AI for Live Summarization & NotebookLM</b><br>"
            "Get your free Google Gemini API key at: <a href='https://aistudio.google.com'>aistudio.google.com</a>"
        )
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        d_layout.addWidget(info)

        key_edit = QLineEdit(self.settings.get("gemini_api_key", os.environ.get("GEMINI_API_KEY", "")))
        key_edit.setPlaceholderText("Paste your Gemini API key (starts with AIza...)")
        key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        d_layout.addWidget(key_edit)

        # Optional OpenAI Key
        d_layout.addWidget(QLabel("Optional OpenAI API Key (or leave blank):"))
        openai_edit = QLineEdit(self.settings.get("openai_api_key", os.environ.get("OPENAI_API_KEY", "")))
        openai_edit.setPlaceholderText("sk-...")
        openai_edit.setEchoMode(QLineEdit.EchoMode.Password)
        d_layout.addWidget(openai_edit)

        btn_row = QHBoxLayout()
        cancel_b = QPushButton("Cancel")
        cancel_b.clicked.connect(diag.reject)
        save_b = QPushButton("Save Keys")
        save_b.setProperty("class", "primaryBtn")
        save_b.clicked.connect(diag.accept)
        btn_row.addWidget(cancel_b)
        btn_row.addWidget(save_b)
        d_layout.addLayout(btn_row)

        if diag.exec():
            new_key = key_edit.text().strip()
            new_openai = openai_edit.text().strip()
            self.settings["gemini_api_key"] = new_key
            self.settings["openai_api_key"] = new_openai
            save_settings(self.settings)
            self.processor.gemini_api_key = new_key
            self.processor.openai_api_key = new_openai
            self.update_ai_banner()
            QMessageBox.information(self, "Saved", "AI API Keys updated successfully!")
