"""
Modern cross-platform CSS stylesheet for PyQt6
Dark and Light themes with slick typography and subtle accents.
"""

DARK_THEME = """
QWidget {
    background-color: #111827;
    color: #f3f4f6;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 14px;
}

/* Sidebar */
QFrame#sidebar {
    background-color: #1f2937;
    border-right: 1px solid #374151;
}

QLabel#appTitle {
    font-size: 18px;
    font-weight: 700;
    color: #60a5fa;
    padding: 8px 4px;
}

QPushButton.navBtn {
    background-color: transparent;
    color: #9ca3af;
    text-align: left;
    padding: 10px 14px;
    border-radius: 8px;
    border: none;
    font-weight: 500;
}

QPushButton.navBtn:hover {
    background-color: #374151;
    color: #f9fafb;
}

QPushButton.navBtn:checked {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: 600;
}

QPushButton.primaryBtn {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: 600;
    padding: 10px 16px;
    border-radius: 8px;
    border: none;
}

QPushButton.primaryBtn:hover {
    background-color: #1d4ed8;
}

QPushButton.secondaryBtn {
    background-color: #374151;
    color: #f3f4f6;
    font-weight: 500;
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid #4b5563;
}

QPushButton.secondaryBtn:hover {
    background-color: #4b5563;
}

QPushButton.dangerBtn {
    background-color: #dc2626;
    color: #ffffff;
    font-weight: 500;
    padding: 8px 14px;
    border-radius: 8px;
    border: none;
}

QPushButton.dangerBtn:hover {
    background-color: #b91c1c;
}

/* Item List / Middle Column */
QFrame#listContainer {
    background-color: #111827;
    border-right: 1px solid #374151;
}

QLineEdit {
    background-color: #1f2937;
    color: #f3f4f6;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 8px 12px;
    selection-background-color: #2563eb;
}

QLineEdit:focus {
    border: 1px solid #60a5fa;
}

QListWidget {
    background-color: transparent;
    border: none;
    padding: 4px;
}

QListWidget::item {
    background-color: #1f2937;
    border-radius: 8px;
    margin-bottom: 6px;
    padding: 10px;
    border: 1px solid #374151;
}

QListWidget::item:hover {
    background-color: #283548;
    border-color: #4b5563;
}

QListWidget::item:selected {
    background-color: #1e3a8a;
    border-color: #3b82f6;
    color: #ffffff;
}

/* Detail Editor Pane */
QFrame#editorContainer {
    background-color: #111827;
}

QLineEdit#titleEdit {
    font-size: 20px;
    font-weight: 700;
    background-color: transparent;
    border: none;
    border-bottom: 2px solid #374151;
    border-radius: 0;
    padding: 8px 4px;
    color: #f9fafb;
}

QLineEdit#titleEdit:focus {
    border-bottom: 2px solid #60a5fa;
}

QTextEdit {
    background-color: #1f2937;
    color: #f3f4f6;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    font-size: 14px;
    line-height: 1.6;
}

QTextEdit:focus {
    border: 1px solid #60a5fa;
}

QTextBrowser#previewBrowser {
    background-color: #1f2937;
    color: #f3f4f6;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 16px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 14px;
}

/* Tabs */
QTabWidget::pane {
    border: none;
}

QTabBar::tab {
    background-color: #1f2937;
    color: #9ca3af;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
}

QTabBar::tab:selected {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: 600;
}

/* Checkbox */
QCheckBox {
    spacing: 8px;
    color: #f3f4f6;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid #6b7280;
    background-color: #1f2937;
}

QCheckBox::indicator:checked {
    background-color: #10b981;
    border-color: #10b981;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #111827;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #374151;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #4b5563;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

def get_markdown_css() -> str:
    return """
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #f3f4f6; line-height: 1.6; }
    h1, h2, h3, h4 { color: #60a5fa; margin-top: 18px; margin-bottom: 8px; }
    h1 { font-size: 24px; border-bottom: 1px solid #374151; padding-bottom: 6px; }
    h2 { font-size: 20px; }
    h3 { font-size: 16px; }
    p { margin: 8px 0; }
    code { background: #374151; color: #38bdf8; padding: 2px 6px; border-radius: 4px; font-family: monospace; }
    pre { background: #111827; padding: 12px; border-radius: 6px; border: 1px solid #374151; }
    blockquote { border-left: 4px solid #3b82f6; margin: 0; padding-left: 12px; color: #9ca3af; }
    ul, ol { padding-left: 24px; }
    li { margin-bottom: 4px; }
    a { color: #38bdf8; text-decoration: none; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; }
    th, td { border: 1px solid #374151; padding: 8px; text-align: left; }
    th { background: #1f2937; color: #60a5fa; }
    """
