"""
KimShell — entry point (Windows only).
"""

import os
import sys

# Ensure local packages resolve correctly regardless of CWD
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import platform

if platform.system() != "Windows":
    print("KimShell поддерживает только Windows.")
    sys.exit(1)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from gui.main_window import KimShellMainWindow
from utils.config import CONFIG


def main() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("KimShell")
    app.setApplicationVersion(CONFIG.VERSION)
    app.setFont(QFont("Segoe UI", 10))

    # Ensure base directories exist
    CONFIG.BASE_DIR  # property call creates dir
    CONFIG.TEMP_DIR
    CONFIG.CACHE_DIR

    window = KimShellMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
