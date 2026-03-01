"""
KimShell Overlay — transparent glowing border around the Brave window.

How it works:
  1. After Brave launches, we poll for its HWND by PID (Brave has multiple
     processes; we find the one that actually has a visible title bar).
  2. A borderless, click-through Qt window is created at the exact same
     screen position as the Brave window.
  3. A QTimer updates position/size every 100 ms so the overlay follows
     the window when the user moves or resizes it.
  4. The overlay paints a glowing green border using QPainter with
     multiple semi-transparent strokes (inner → outer glow layers).
  5. When Brave closes the overlay destroys itself.

Requirements: pywin32 (pip install pywin32)
"""

import math
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget

try:
    import win32gui
    import win32process
    import win32con
    _WIN32_OK = True
except ImportError:
    _WIN32_OK = False

try:
    from PyQt6.QtSvg import QSvgRenderer
    _SVG_OK = True
except ImportError:
    _SVG_OK = False

from utils.helpers import logger

# Overlay visual constants
_BORDER       = 3      # px — main border width
_GLOW_LAYERS  = 5      # number of glow rings outside the border
_GLOW_SPREAD  = 4      # px per glow layer
_COLOR_MAIN   = QColor(0, 255, 136, 220)   # #00ff88 opaque
_COLOR_GLOW   = QColor(0, 255, 136)        # glow base (alpha set per layer)
_BADGE_SIZE   = 32     # px — corner badge


class BraveOverlay(QWidget):
    """
    Transparent, click-through window that draws a glowing border
    around the Brave browser window.
    """

    def __init__(self, brave_pid: int, logo_path: Optional[Path] = None) -> None:
        super().__init__(None)  # top-level, no parent

        self._pid        = brave_pid
        self._hwnd: int  = 0
        self._logo_pix: Optional[QPixmap] = None
        self._tick       = 0   # for pulse animation

        # Load logo for corner badge
        if logo_path and _SVG_OK and logo_path.is_file():
            r = QSvgRenderer(str(logo_path))
            if r.isValid():
                pix = QPixmap(_BADGE_SIZE, _BADGE_SIZE)
                pix.fill(Qt.GlobalColor.transparent)
                p = QPainter(pix)
                r.render(p)
                p.end()
                self._logo_pix = pix

        # Window flags: frameless, always on top, transparent to mouse
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool                    # no taskbar entry
            | Qt.WindowType.WindowTransparentForInput  # clicks pass through
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Find Brave window (retry up to ~5s)
        self._find_attempts = 0
        self._find_timer = QTimer(self)
        self._find_timer.timeout.connect(self._try_find_hwnd)
        self._find_timer.start(300)

        # Track position + animate glow
        self._track_timer = QTimer(self)
        self._track_timer.timeout.connect(self._update)
        # Started after hwnd is found

    # ── Window discovery ──────────────────────────────────────────────────────

    def _try_find_hwnd(self) -> None:
        if not _WIN32_OK:
            self._find_timer.stop()
            return

        self._find_attempts += 1
        hwnd = self._find_brave_hwnd(self._pid)
        if hwnd:
            self._hwnd = hwnd
            self._find_timer.stop()
            self._track_timer.start(100)
            self._update()
            self.show()
            logger.info(f"Overlay: прикреплён к HWND {hwnd:#010x}")
        elif self._find_attempts > 20:  # 6 seconds
            self._find_timer.stop()
            logger.warning("Overlay: окно Brave не найдено, оверлей отключён")

    @staticmethod
    def _find_brave_hwnd(pid: int) -> int:
        """
        Walk all top-level windows; return the first visible one
        belonging to our PID that has a non-empty title (= main window).
        """
        result = 0

        def _cb(hwnd, _):
            nonlocal result
            if not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                _, wpid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            # Match any process in the Brave process group
            if wpid == pid:
                title = win32gui.GetWindowText(hwnd)
                if title:
                    result = hwnd
                    return False  # stop enumeration
            return True

        try:
            win32gui.EnumWindows(_cb, None)
        except Exception:
            pass
        return result

    # ── Position tracking ─────────────────────────────────────────────────────

    def _update(self) -> None:
        if not self._hwnd:
            return

        # Check if Brave window still exists
        if not win32gui.IsWindow(self._hwnd):
            self.close()
            return

        try:
            rect = win32gui.GetWindowRect(self._hwnd)
        except Exception:
            self.close()
            return

        x, y, r, b = rect
        w = r - x
        h = b - y

        if w <= 0 or h <= 0:
            return

        # Total spread we need to paint outside the window
        spread = _GLOW_LAYERS * _GLOW_SPREAD + _BORDER + 2

        self.setGeometry(
            x - spread,
            y - spread,
            w + spread * 2,
            h + spread * 2,
        )

        # Animate glow pulse
        self._tick = (self._tick + 1) % 60
        self.update()   # trigger paintEvent

    # ── Drawing ───────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        spread = _GLOW_LAYERS * _GLOW_SPREAD + _BORDER + 2
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Pulse factor: sin wave between 0.6 and 1.0
        pulse = 0.6 + 0.4 * (math.sin(self._tick * math.pi / 30) * 0.5 + 0.5)

        # Draw glow layers from outer (transparent) → inner (opaque)
        for i in range(_GLOW_LAYERS, 0, -1):
            alpha = int(30 * (1 - i / _GLOW_LAYERS) * pulse)
            offset = spread - (_GLOW_LAYERS - i) * _GLOW_SPREAD
            color = QColor(_COLOR_GLOW)
            color.setAlpha(alpha)
            pen = QPen(color, (_GLOW_LAYERS - i + 1) * 2)
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(
                offset, offset,
                self.width()  - offset * 2,
                self.height() - offset * 2,
            )

        # Main crisp border
        main_color = QColor(_COLOR_MAIN)
        main_color.setAlpha(int(220 * pulse))
        pen = QPen(main_color, _BORDER)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen)
        p.drawRect(
            spread, spread,
            self.width()  - spread * 2,
            self.height() - spread * 2,
        )

        # Corner accents (small tick marks)
        tick = 18
        p.setPen(QPen(QColor(0, 255, 136, int(255 * pulse)), 2))
        corners = [
            (spread, spread),
            (self.width() - spread, spread),
            (spread, self.height() - spread),
            (self.width() - spread, self.height() - spread),
        ]
        for cx, cy in corners:
            sx = 1 if cx == spread else -1
            sy = 1 if cy == spread else -1
            p.drawLine(cx, cy, cx + sx * tick, cy)
            p.drawLine(cx, cy, cx, cy + sy * tick)

        # Top-left badge: KimShell logo
        if self._logo_pix:
            badge_x = spread + 8
            badge_y = spread + 8
            p.setOpacity(0.85 * pulse)
            p.drawPixmap(badge_x, badge_y, self._logo_pix)
            p.setOpacity(1.0)

            # "KimShell" label next to badge
            p.setPen(QColor(0, 255, 136, int(200 * pulse)))
            font = p.font()
            font.setFamily("Consolas")
            font.setPointSize(8)
            font.setBold(True)
            p.setFont(font)
            p.drawText(
                badge_x + _BADGE_SIZE + 6,
                badge_y + _BADGE_SIZE // 2 + 4,
                "KimShell  ·  Protected"
            )

        p.end()
