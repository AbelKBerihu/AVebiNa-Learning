import os
import sys
from datetime import datetime
import markdown
from typing import Optional, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QLabel, QPushButton, QLineEdit, QTextEdit, QTextBrowser,
    QListWidget, QListWidgetItem, QCheckBox, QTabWidget,
    QMessageBox, QFrame, QButtonGroup, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QFont, QColor

from app.models import Item, utc_now_iso
from app.storage import Storage
from app.sync_engine import SyncEngine
from app.config import load_settings, save_settings
from app.gui.theme import DARK_THEME, get_markdown_css
from app.gui.settings_dialog import SettingsDialog

class SyncWorker(QThread):
    sync_finished = pyqtSignal(bool, str)

    def __init__(self, sync_engine: SyncEngine):
        super().__init__()
        self.sync_engine = sync_engine

    def run(self):
        success, msg = self.sync_engine.perform_sync()
        self.sync_finished.emit(success, msg)

class MainWindow(QMainWindow):
    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage
        self.settings = load_settings()
        self.setWindowTitle("CrossSync - Notes & Tasks")
        self.resize(1150, 750)
        self.setStyleSheet(DARK_THEME)

        self.sync_engine = SyncEngine(
            storage=self.storage,
            server_url=self.settings.get("server_url", "http://127.0.0.1:8765"),
            sync_token=self.settings.get("sync_token", "cross-sync-secret-key"),
            client_id=self.settings.get("client_id", "desktop-client")
        )

        self.current_item: Optional[Item] = None
        self.current_filter = "all"  # all, note, task, pinned, trash
        self.active_tag_filter: Optional[str] = None
        self.is_loading_item = False
        self.sync_thread: Optional[SyncWorker] = None

        # Debounce auto-save timer
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(450)
        self.save_timer.timeout.connect(self.save_current_item)

        # Background auto-sync timer
        self.auto_sync_timer = QTimer()
        self.auto_sync_timer.timeout.connect(self.trigger_background_sync)
        self._update_auto_sync_timer()

        self.init_ui()
        self.refresh_items_list()
        self.refresh_tags_sidebar()

        # Initial startup sync
        QTimer.single_shot(1000, self.trigger_background_sync)

    def _update_auto_sync_timer(self):
        self.auto_sync_timer.stop()
        if self.settings.get("auto_sync_enabled", True):
            interval = self.settings.get("auto_sync_interval", 15) * 1000
            self.auto_sync_timer.start(interval)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # 1. Left Sidebar
        sidebar = self._create_sidebar()
        splitter.addWidget(sidebar)

        # 2. Middle List Column
        list_pane = self._create_list_pane()
        splitter.addWidget(list_pane)

        # 3. Right Editor / Detail Column
        editor_pane = self._create_editor_pane()
        splitter.addWidget(editor_pane)

        splitter.setSizes([220, 320, 610])
        main_layout.addWidget(splitter)

    # ------------------ SIDEBAR ------------------
    def _create_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(8)

        # App Brand
        app_title = QLabel("✦ CrossSync")
        app_title.setObjectName("appTitle")
        layout.addWidget(app_title)

        # New Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        new_note_btn = QPushButton("+ Note")
        new_note_btn.setProperty("class", "primaryBtn")
        new_note_btn.clicked.connect(lambda: self.create_new_item("note"))
        btn_layout.addWidget(new_note_btn)

        new_task_btn = QPushButton("+ Task")
        new_task_btn.setProperty("class", "secondaryBtn")
        new_task_btn.clicked.connect(lambda: self.create_new_item("task"))
        btn_layout.addWidget(new_task_btn)

        layout.addLayout(btn_layout)

        # AI Meeting / Lecture Record Button
        ai_record_btn = QPushButton("🎙 Live AI Meeting & Study")
        ai_record_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
                color: #ffffff;
                font-weight: bold;
                padding: 10px 14px;
                border-radius: 8px;
                border: none;
                text-align: center;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #6d28d9);
            }
        """)
        ai_record_btn.clicked.connect(self.open_learning_companion)
        layout.addWidget(ai_record_btn)

        layout.addSpacing(10)

        # Navigation Filters
        self.nav_btn_group = QButtonGroup(self)
        self.nav_btn_group.setExclusive(True)

        nav_items = [
            ("All Items", "all"),
            ("Notes", "note"),
            ("Tasks", "task"),
            ("Starred", "pinned"),
            ("Trash", "trash")
        ]

        for text, key in nav_items:
            btn = QPushButton(text)
            btn.setProperty("class", "navBtn")
            btn.setCheckable(True)
            if key == "all":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, k=key: self.set_navigation_filter(k))
            self.nav_btn_group.addButton(btn)
            layout.addWidget(btn)

        layout.addSpacing(12)
        tags_header = QLabel("TAGS")
        tags_header.setStyleSheet("color: #6b7280; font-size: 11px; font-weight: bold; padding: 4px;")
        layout.addWidget(tags_header)

        # Tag container
        self.tags_scroll = QScrollArea()
        self.tags_scroll.setWidgetResizable(True)
        self.tags_scroll.setStyleSheet("background: transparent; border: none;")
        self.tags_container = QWidget()
        self.tags_layout = QVBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(0, 0, 0, 0)
        self.tags_layout.setSpacing(4)
        self.tags_layout.addStretch()
        self.tags_scroll.setWidget(self.tags_container)
        layout.addWidget(self.tags_scroll, 1)

        # Bottom Sync & Settings Bar
        layout.addSpacing(6)
        status_box = QFrame()
        status_box.setStyleSheet("background-color: #111827; border-radius: 8px; padding: 8px;")
        sb_layout = QVBoxLayout(status_box)
        sb_layout.setContentsMargins(4, 4, 4, 4)
        sb_layout.setSpacing(6)

        # Status indicator row
        stat_row = QHBoxLayout()
        self.sync_dot = QLabel("●")
        self.sync_dot.setStyleSheet("color: #10b981; font-size: 14px;")
        self.sync_status_lbl = QLabel("Ready")
        self.sync_status_lbl.setStyleSheet("color: #9ca3af; font-size: 12px;")
        stat_row.addWidget(self.sync_dot)
        stat_row.addWidget(self.sync_status_lbl)
        stat_row.addStretch()
        sb_layout.addLayout(stat_row)

        action_row = QHBoxLayout()
        self.sync_btn = QPushButton("Sync Now")
        self.sync_btn.setProperty("class", "secondaryBtn")
        self.sync_btn.setStyleSheet("padding: 5px 10px; font-size: 12px;")
        self.sync_btn.clicked.connect(self.trigger_background_sync)
        action_row.addWidget(self.sync_btn)

        settings_btn = QPushButton("⚙")
        settings_btn.setProperty("class", "secondaryBtn")
        settings_btn.setStyleSheet("padding: 5px 10px; font-size: 12px;")
        settings_btn.clicked.connect(self.open_settings)
        action_row.addWidget(settings_btn)
        sb_layout.addLayout(action_row)

        layout.addWidget(status_box)
        return sidebar

    # ------------------ MIDDLE LIST PANE ------------------
    def _create_list_pane(self) -> QWidget:
        pane = QFrame()
        pane.setObjectName("listContainer")
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(10)

        # Search Bar
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Search notes and tasks...")
        self.search_edit.textChanged.connect(self.refresh_items_list)
        layout.addWidget(self.search_edit)

        # Active tag chip indicator
        self.tag_banner = QFrame()
        self.tag_banner.setStyleSheet("background: #1e3a8a; border-radius: 6px; padding: 4px 8px;")
        tb_layout = QHBoxLayout(self.tag_banner)
        tb_layout.setContentsMargins(4, 2, 4, 2)
        self.tag_banner_lbl = QLabel("Tag: ")
        self.tag_banner_lbl.setStyleSheet("color: #93c5fd; font-size: 12px;")
        tb_layout.addWidget(self.tag_banner_lbl)
        clear_tag_btn = QPushButton("✕")
        clear_tag_btn.setStyleSheet("background: transparent; color: #93c5fd; border: none; font-weight: bold;")
        clear_tag_btn.clicked.connect(self.clear_tag_filter)
        tb_layout.addWidget(clear_tag_btn)
        self.tag_banner.hide()
        layout.addWidget(self.tag_banner)

        # List Widget
        self.items_list = QListWidget()
        self.items_list.itemClicked.connect(self.on_item_selected)
        layout.addWidget(self.items_list)

        return pane

    # ------------------ RIGHT EDITOR PANE ------------------
    def _create_editor_pane(self) -> QWidget:
        pane = QFrame()
        pane.setObjectName("editorContainer")
        self.editor_layout = QVBoxLayout(pane)
        self.editor_layout.setContentsMargins(20, 20, 20, 20)
        self.editor_layout.setSpacing(12)

        # Empty placeholder state
        self.empty_lbl = QLabel("Select an item to view or create a new one.")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet("color: #6b7280; font-size: 16px;")
        self.editor_layout.addWidget(self.empty_lbl)

        # Main editor container (hidden when nothing selected)
        self.editor_content = QWidget()
        content_layout = QVBoxLayout(self.editor_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        # Top Bar: Pin, Type Badge, Task Status, Delete
        top_bar = QHBoxLayout()
        
        self.type_label = QLabel("NOTE")
        self.type_label.setStyleSheet("background: #374151; color: #60a5fa; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold;")
        top_bar.addWidget(self.type_label)

        self.task_check = QCheckBox("Completed")
        self.task_check.setStyleSheet("font-weight: 600; color: #10b981;")
        self.task_check.stateChanged.connect(self.on_task_check_changed)
        top_bar.addWidget(self.task_check)

        self.pin_btn = QPushButton("★ Starred")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setProperty("class", "secondaryBtn")
        self.pin_btn.clicked.connect(self.on_pin_toggled)
        top_bar.addWidget(self.pin_btn)

        top_bar.addStretch()

        self.save_badge = QLabel("Saved")
        self.save_badge.setStyleSheet("color: #10b981; font-size: 12px;")
        top_bar.addWidget(self.save_badge)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setProperty("class", "dangerBtn")
        self.delete_btn.clicked.connect(self.on_delete_clicked)
        top_bar.addWidget(self.delete_btn)

        content_layout.addLayout(top_bar)

        # Title Edit
        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("titleEdit")
        self.title_edit.setPlaceholderText("Title...")
        self.title_edit.textChanged.connect(self.on_field_edited)
        content_layout.addWidget(self.title_edit)

        # Tags Edit
        tags_row = QHBoxLayout()
        tags_row.addWidget(QLabel("Tags:"))
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("work, personal, project (comma separated)")
        self.tags_edit.textChanged.connect(self.on_field_edited)
        tags_row.addWidget(self.tags_edit)
        content_layout.addLayout(tags_row)

        # Tabs: Edit & Markdown Preview
        self.tabs = QTabWidget()
        
        self.text_editor = QTextEdit()
        self.text_editor.setPlaceholderText("Write your notes or task details in Markdown...")
        self.text_editor.textChanged.connect(self.on_field_edited)
        self.tabs.addTab(self.text_editor, "Edit")

        self.preview_browser = QTextBrowser()
        self.preview_browser.setObjectName("previewBrowser")
        self.tabs.addTab(self.preview_browser, "Preview")
        self.tabs.currentChanged.connect(self.on_tab_changed)

        content_layout.addWidget(self.tabs, 1)

        self.editor_content.hide()
        self.editor_layout.addWidget(self.editor_content)

        return pane

    # ------------------ EVENT HANDLERS & LOGIC ------------------
    def open_learning_companion(self):
        from app.gui.learning_window import LearningWindow
        self.learning_window = LearningWindow(self.storage)
        self.learning_window.show()

    def set_navigation_filter(self, key: str):
        self.current_filter = key
        self.refresh_items_list()

    def set_tag_filter(self, tag: str):
        self.active_tag_filter = tag
        self.tag_banner_lbl.setText(f"Tag: #{tag}")
        self.tag_banner.show()
        self.refresh_items_list()

    def clear_tag_filter(self):
        self.active_tag_filter = None
        self.tag_banner.hide()
        self.refresh_items_list()

    def refresh_tags_sidebar(self):
        # Clear existing tags in layout
        while self.tags_layout.count() > 1:
            child = self.tags_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        tags = self.storage.get_all_tags()
        for t in tags:
            tag_btn = QPushButton(f"#{t}")
            tag_btn.setProperty("class", "navBtn")
            tag_btn.setStyleSheet("padding: 6px 10px; font-size: 13px; color: #93c5fd;")
            tag_btn.clicked.connect(lambda checked, tag=t: self.set_tag_filter(tag))
            self.tags_layout.insertWidget(self.tags_layout.count() - 1, tag_btn)

    def refresh_items_list(self):
        search_query = self.search_edit.text().strip()
        include_deleted = (self.current_filter == "trash")
        
        filter_type = None
        if self.current_filter in ("note", "task"):
            filter_type = self.current_filter

        items = self.storage.get_items(
            item_type=filter_type,
            include_deleted=include_deleted,
            tag=self.active_tag_filter,
            search=search_query if search_query else None
        )

        if self.current_filter == "pinned":
            items = [it for it in items if it.is_pinned and not it.is_deleted]
        elif self.current_filter == "trash":
            items = [it for it in items if it.is_deleted]

        self.items_list.clear()

        for item in items:
            list_item = QListWidgetItem()
            list_item.setData(Qt.ItemDataRole.UserRole, item.id)

            # Format item display card
            icon_prefix = "★ " if item.is_pinned else ""
            type_symbol = "📝 " if item.item_type == "note" else ("☑ " if item.status == "completed" else "☐ ")
            title_text = item.title if item.title else "Untitled"

            snippet = item.content.replace("\n", " ").strip()
            if len(snippet) > 45:
                snippet = snippet[:45] + "..."

            card_text = f"{icon_prefix}{type_symbol} {title_text}\n  {snippet}"
            if item.tags:
                card_text += f"\n  [{item.tags}]"

            list_item.setText(card_text)
            self.items_list.addItem(list_item)

            if self.current_item and self.current_item.id == item.id:
                list_item.setSelected(True)

    def create_new_item(self, item_type: str):
        new_item = Item(
            item_type=item_type,
            title=f"New {item_type.capitalize()}",
            content="",
            status="pending" if item_type == "task" else "active"
        )
        self.storage.save_item(new_item, mark_dirty=True)
        self.refresh_items_list()
        self.load_item_into_editor(new_item)
        self.title_edit.setFocus()
        self.title_edit.selectAll()
        self.trigger_background_sync()

    def on_item_selected(self, list_item: QListWidgetItem):
        item_id = list_item.data(Qt.ItemDataRole.UserRole)
        item = self.storage.get_item(item_id)
        if item:
            self.load_item_into_editor(item)

    def load_item_into_editor(self, item: Item):
        self.is_loading_item = True
        self.current_item = item

        self.empty_lbl.hide()
        self.editor_content.show()

        self.title_edit.setText(item.title)
        self.tags_edit.setText(item.tags)
        self.text_editor.setPlainText(item.content)
        self.pin_btn.setChecked(item.is_pinned)

        if item.item_type == "task":
            self.type_label.setText("TASK")
            self.type_label.setStyleSheet("background: #065f46; color: #34d399; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold;")
            self.task_check.show()
            self.task_check.setChecked(item.status == "completed")
        else:
            self.type_label.setText("NOTE")
            self.type_label.setStyleSheet("background: #1e3a8a; color: #60a5fa; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold;")
            self.task_check.hide()

        if item.is_deleted:
            self.delete_btn.setText("Restore")
            self.delete_btn.setProperty("class", "primaryBtn")
        else:
            self.delete_btn.setText("Delete")
            self.delete_btn.setProperty("class", "dangerBtn")

        self.delete_btn.style().unpolish(self.delete_btn)
        self.delete_btn.style().polish(self.delete_btn)

        self.update_preview()
        self.save_badge.setText("Saved")
        self.is_loading_item = False

    def on_field_edited(self):
        if self.is_loading_item or not self.current_item:
            return
        self.save_badge.setText("Saving...")
        self.save_badge.setStyleSheet("color: #f59e0b;")
        self.save_timer.start()

    def on_task_check_changed(self, state):
        if self.is_loading_item or not self.current_item:
            return
        self.current_item.status = "completed" if self.task_check.isChecked() else "pending"
        self.save_current_item()
        self.refresh_items_list()

    def on_pin_toggled(self):
        if not self.current_item:
            return
        self.current_item.is_pinned = self.pin_btn.isChecked()
        self.save_current_item()
        self.refresh_items_list()

    def on_delete_clicked(self):
        if not self.current_item:
            return
        if self.current_item.is_deleted:
            # Restore
            self.storage.restore_item(self.current_item.id)
            self.current_item.is_deleted = False
        else:
            # Soft Delete
            self.storage.soft_delete_item(self.current_item.id)
            self.current_item.is_deleted = True

        self.refresh_items_list()
        self.editor_content.hide()
        self.empty_lbl.show()
        self.current_item = None
        self.trigger_background_sync()

    def save_current_item(self):
        if not self.current_item:
            return
        self.current_item.title = self.title_edit.text()
        self.current_item.tags = self.tags_edit.text()
        self.current_item.content = self.text_editor.toPlainText()
        self.storage.save_item(self.current_item, mark_dirty=True)
        self.save_badge.setText("Saved")
        self.save_badge.setStyleSheet("color: #10b981;")
        self.refresh_items_list()
        self.refresh_tags_sidebar()
        self.trigger_background_sync()

    def on_tab_changed(self, index):
        if index == 1:  # Preview tab
            self.update_preview()

    def update_preview(self):
        raw_text = self.text_editor.toPlainText()
        html = markdown.markdown(raw_text, extensions=['fenced_code', 'tables'])
        styled_html = f"<style>{get_markdown_css()}</style>{html}"
        self.preview_browser.setHtml(styled_html)

    # ------------------ SYNC MANAGEMENT ------------------
    def trigger_background_sync(self):
        if self.sync_thread and self.sync_thread.isRunning():
            return
        
        self.sync_dot.setStyleSheet("color: #f59e0b;")
        self.sync_status_lbl.setText("Syncing...")
        self.sync_btn.setEnabled(False)

        self.sync_thread = SyncWorker(self.sync_engine)
        self.sync_thread.sync_finished.connect(self.on_sync_finished)
        self.sync_thread.start()

    def on_sync_finished(self, success: bool, message: str):
        self.sync_btn.setEnabled(True)
        if success:
            self.sync_dot.setStyleSheet("color: #10b981;")
            self.sync_status_lbl.setText("Synced")
            # Refresh list in case server sent new or updated items
            cur_id = self.current_item.id if self.current_item else None
            self.refresh_items_list()
            self.refresh_tags_sidebar()
            if cur_id:
                updated = self.storage.get_item(cur_id)
                if updated and not self.save_timer.isActive():
                    self.load_item_into_editor(updated)
        else:
            self.sync_dot.setStyleSheet("color: #ef4444;")
            self.sync_status_lbl.setText("Offline / Error")

    def open_settings(self):
        dialog = SettingsDialog(self, self.settings, self.sync_engine)
        if dialog.exec():
            save_settings(self.settings)
            self.sync_engine.update_config(
                self.settings.get("server_url", "http://127.0.0.1:8765"),
                self.settings.get("sync_token", "")
            )
            self._update_auto_sync_timer()
            self.trigger_background_sync()
