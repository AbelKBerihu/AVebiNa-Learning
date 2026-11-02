#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from app.config import get_db_path
from app.storage import Storage
from app.gui.learning_window import LearningWindow

def main():
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("LearnEcho")
    app.setOrganizationName("CrossSync")

    storage = Storage(get_db_path())
    window = LearningWindow(storage)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
