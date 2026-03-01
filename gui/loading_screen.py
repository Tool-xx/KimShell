"""Animated loading screen."""

import math

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import (QGraphicsDropShadowEffect, QLabel, QProgressBar,
                             QVBoxLayout, QWidget)


class LoadingScreen(QWidget):

    _MESSAGES = [
        "Инициализация модуля безопасности…",
        "Генерация виртуального профиля железа…",
        "Маскировка аппаратных отпечатков…",
        "Проверка сети / VPN…",
        "Загрузка Brave Browser…",
        "Создание JS-расширения…",
        "Система готова к запуску.",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(520, 420)
        self._step = 0
        self._timer: QTimer | None = None
        self._setup()

    def _setup(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 40, 40, 40)

        card = QWidget()
        card.setStyleSheet("background:#151520; border-radius:20px; border:1px solid #222;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 255, 136, 50))
        shadow.setOffset(0, 0)
        card.setGraphicsEffect(shadow)

        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(36, 36, 36, 36)
        vbox.setSpacing(12)

        self._logo = _SpinLogo()
        vbox.addWidget(self._logo, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel("KimShell")
        title.setStyleSheet("font-size:34px; font-weight:bold; color:#00ff88; letter-spacing:4px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(title)

        sub = QLabel("Secure Browser Environment v2.0")
        sub.setStyleSheet("color:#444; font-size:10px; letter-spacing:2px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(sub)

        self._msg = QLabel("Инициализация…")
        self._msg.setStyleSheet("color:#00ff88; font-family:Consolas; font-size:11px;")
        self._msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(self._msg)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        vbox.addWidget(self.progress)

        outer.addWidget(card)

    def start(self) -> None:
        self._logo.start()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(700)

    def _tick(self) -> None:
        if self._step < len(self._MESSAGES):
            self._msg.setText(f"▶  {self._MESSAGES[self._step]}")
            self._step += 1
        else:
            self._timer and self._timer.stop()

    def finish(self) -> None:
        self.progress.setValue(100)
        self._msg.setText("▶  Готово.")
        QTimer.singleShot(400, self.close)


class _SpinLogo(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(80, 80)
        self._angle = 0
        self._timer: QTimer | None = None

    def start(self) -> None:
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.start(16)

    def _rotate(self) -> None:
        self._angle = (self._angle + 4) % 360
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.rect().center()

        p.setPen(QPen(QColor(0, 255, 136), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, 35, 35)

        rad = math.radians(self._angle)
        x = c.x() + 35 * math.cos(rad)
        y = c.y() + 35 * math.sin(rad)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 255, 136)))
        p.drawEllipse(int(x) - 5, int(y) - 5, 10, 10)

        p.end()
