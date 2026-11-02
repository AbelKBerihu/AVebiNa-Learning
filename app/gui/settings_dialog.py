from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt
from app.sync_engine import SyncEngine

class SettingsDialog(QDialog):
    def __init__(self, parent, settings: dict, sync_engine: SyncEngine):
        super().__init__(parent)
        self.setWindowTitle("Sync & App Settings")
        self.setMinimumWidth(450)
        self.settings = settings
        self.sync_engine = sync_engine

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Cloud & Device Synchronization")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #60a5fa;")
        layout.addWidget(title)

        desc = QLabel(
            "Configure your synchronization server to keep your notes and tasks "
            "synchronized between your Windows and Linux machines in real-time."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #9ca3af; font-size: 13px;")
        layout.addWidget(desc)

        # Server URL
        layout.addWidget(QLabel("Sync Server URL:"))
        self.url_edit = QLineEdit(self.settings.get("server_url", "http://127.0.0.1:8765"))
        self.url_edit.setPlaceholderText("http://192.168.1.100:8765")
        layout.addWidget(self.url_edit)

        # Sync Token
        layout.addWidget(QLabel("Security Sync Token / Passkey:"))
        self.token_edit = QLineEdit(self.settings.get("sync_token", ""))
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("Enter shared secret key")
        layout.addWidget(self.token_edit)

        # Test Connection button
        test_row = QHBoxLayout()
        self.test_btn = QPushButton("Test Server Connection")
        self.test_btn.setProperty("class", "secondaryBtn")
        self.test_btn.clicked.connect(self.test_connection)
        self.test_status_lbl = QLabel("")
        self.test_status_lbl.setStyleSheet("font-size: 12px;")
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_status_lbl)
        test_row.addStretch()
        layout.addLayout(test_row)

        # Auto sync
        self.auto_sync_check = QCheckBox("Enable Automatic Background Sync")
        self.auto_sync_check.setChecked(self.settings.get("auto_sync_enabled", True))
        layout.addWidget(self.auto_sync_check)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("Sync Interval (seconds):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 600)
        self.interval_spin.setValue(self.settings.get("auto_sync_interval", 15))
        interval_row.addWidget(self.interval_spin)
        interval_row.addStretch()
        layout.addLayout(interval_row)

        layout.addStretch()

        # Dialog Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.setProperty("class", "primaryBtn")
        save_btn.clicked.connect(self.save_and_accept)
        btn_box.addWidget(save_btn)

        layout.addLayout(btn_box)

    def test_connection(self):
        url = self.url_edit.text().strip()
        token = self.token_edit.text().strip()
        self.test_status_lbl.setText("Testing...")
        self.test_status_lbl.setStyleSheet("color: #f59e0b;")
        
        # Temporary test using sync engine
        old_url, old_token = self.sync_engine.server_url, self.sync_engine.sync_token
        self.sync_engine.update_config(url, token)
        success, msg = self.sync_engine.test_connection()
        self.sync_engine.update_config(old_url, old_token)

        if success:
            self.test_status_lbl.setText("✓ " + msg)
            self.test_status_lbl.setStyleSheet("color: #10b981; font-weight: bold;")
        else:
            self.test_status_lbl.setText("✗ " + msg)
            self.test_status_lbl.setStyleSheet("color: #ef4444;")

    def save_and_accept(self):
        self.settings["server_url"] = self.url_edit.text().strip()
        self.settings["sync_token"] = self.token_edit.text().strip()
        self.settings["auto_sync_enabled"] = self.auto_sync_check.isChecked()
        self.settings["auto_sync_interval"] = self.interval_spin.value()
        self.accept()
