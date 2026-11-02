#!/usr/bin/env python3
import sys
import os

# Ensure the root package is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from app.config import get_db_path
from app.storage import Storage
from app.gui.main_window import MainWindow

def main():
    # Enable High DPI scaling
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("CrossSync")
    app.setOrganizationName("CrossSync")

    storage = Storage(get_db_path())
    window = MainWindow(storage)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
