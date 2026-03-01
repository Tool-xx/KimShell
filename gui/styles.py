"""KimShell dark theme stylesheet."""

DARK_THEME = """
QMainWindow, QDialog {
    background-color: #0a0a0f;
}

QWidget {
    background-color: #0a0a0f;
    color: #e0e0e0;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}

QPushButton {
    background-color: #151520;
    color: #00ff88;
    border: 2px solid #00ff88;
    border-radius: 8px;
    padding: 10px 22px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover    { background-color: #00ff88; color: #0a0a0f; }
QPushButton:pressed  { background-color: #00cc6a; }
QPushButton:disabled { background-color: #1a1a25; color: #555; border-color: #333; }

QLabel {
    color: #e0e0e0;
    background: transparent;
}

QProgressBar {
    border: 2px solid #222;
    border-radius: 10px;
    text-align: center;
    color: transparent;
    background-color: #0a0a0f;
    height: 12px;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #00ff88, stop:1 #00ccff);
    border-radius: 10px;
}

QCheckBox { spacing: 8px; color: #ccc; }
QCheckBox::indicator {
    width: 18px; height: 18px;
    border: 2px solid #333; border-radius: 4px; background: #151520;
}
QCheckBox::indicator:checked { background: #00ff88; border-color: #00ff88; }

QGroupBox {
    border: 1px solid #222; border-radius: 8px;
    margin-top: 12px; padding-top: 12px;
    font-weight: bold; color: #888;
}

QTextEdit {
    background-color: #0d0d12;
    color: #00ff88;
    border: 1px solid #222; border-radius: 8px; padding: 8px;
    font-family: 'Consolas', monospace; font-size: 11px;
}

QScrollBar:vertical {
    background: #0d0d12; width: 8px; border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #333; border-radius: 4px; min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

QSplitter::handle { background-color: #1a1a25; width: 2px; }

QMessageBox { background-color: #151520; }
QMessageBox QLabel { color: #e0e0e0; }
QMessageBox QPushButton { min-width: 80px; }
"""
