"""
Main window — Windows only.
- Removed: drag & drop quarantine widget
- Added: SVG logo as semi-transparent background in log panel

Bugs fixed vs previous version:
  - LogPanel.paintEvent was opening QPainter on self.viewport() from inside
    the widget's own paintEvent → crash / blank. Fixed with viewport eventFilter.
  - QColor was imported but unused → removed.
  - _check_alive called poll() twice → stored result once.
  - QSvgRenderer import wrapped in try/except so missing package doesn't crash app.
"""

import os
import subprocess
from dataclasses import asdict
from pathlib import Path

from PyQt6.QtCore import Qt, QEvent, QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import (QCheckBox, QFrame, QGroupBox, QHBoxLayout,
                             QLabel, QMainWindow, QMessageBox, QPushButton,
                             QSplitter, QTextEdit, QVBoxLayout, QWidget)

# SVG support is optional — wrap import so missing package shows friendly error
try:
    from PyQt6.QtSvg import QSvgRenderer
    _SVG_OK = True
except ImportError:
    _SVG_OK = False

from core.brave_manager import BraveManager
from core.cleanup import CleanupManager
from core.hardware_spoof import HardwareProfile, HardwareSpoofer
from core.js_injector import JSInjector
from core.extension_manager import ExtensionManager
from core.network_checker import NetworkChecker, NetworkStatus
from gui.loading_screen import LoadingScreen
from gui.styles import DARK_THEME
from utils.config import CONFIG
from utils.helpers import generate_session_id, logger


# ── Viewport event filter that draws the logo behind text ─────────────────────

class _LogoBgFilter(QObject):
    """
    Installs on QTextEdit.viewport() and draws the SVG logo
    semi-transparently AFTER the viewport's own paint (so text is on top).
    """

    def __init__(self, viewport: QObject, logo_path: Path) -> None:
        super().__init__(viewport)
        self._renderer = None
        self._pixmap_cache: QPixmap | None = None
        self._cache_size: int = 0

        if _SVG_OK and logo_path.is_file():
            r = QSvgRenderer(str(logo_path))
            if r.isValid():
                self._renderer = r

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Paint and self._renderer:
            # Let the viewport paint text normally first
            result = super().eventFilter(obj, event)

            vp   = obj  # the viewport widget
            rect = vp.rect()
            size = int(min(rect.width(), rect.height()) * 0.55)

            # Rebuild pixmap only when size changes (avoid per-frame SVG render)
            if size != self._cache_size or self._pixmap_cache is None:
                pix = QPixmap(size, size)
                pix.fill(Qt.GlobalColor.transparent)
                p = QPainter(pix)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                self._renderer.render(p)
                p.end()
                self._pixmap_cache = pix
                self._cache_size   = size

            x = (rect.width()  - size) // 2
            y = (rect.height() - size) // 2

            p = QPainter(vp)
            p.setOpacity(0.07)
            p.drawPixmap(x, y, self._pixmap_cache)
            p.end()

            return result

        return super().eventFilter(obj, event)


# ── Log panel ─────────────────────────────────────────────────────────────────

class LogPanel(QTextEdit):
    """Read-only log view with semi-transparent logo watermark."""

    def __init__(self, logo_path: Path) -> None:
        super().__init__()
        self.setReadOnly(True)
        # Install filter on the viewport — correct place for background painting
        self._bg = _LogoBgFilter(self.viewport(), logo_path)
        self.viewport().installEventFilter(self._bg)


# ── Init worker thread ────────────────────────────────────────────────────────

class InitThread(QThread):
    status   = pyqtSignal(str)
    progress = pyqtSignal(int)
    network  = pyqtSignal(object)
    profile  = pyqtSignal(object)
    done     = pyqtSignal(bool, str)

    def __init__(self, session_id: str, brave_mgr: BraveManager) -> None:
        super().__init__()
        self._session = session_id
        self.spoofer  = HardwareSpoofer()
        self._net     = NetworkChecker()
        self._brave   = brave_mgr   # shared — writes brave_exe into MainWindow's instance
        self._ext_mgr = ExtensionManager()

    def run(self) -> None:
        try:
            self.status.emit("Проверка сети / VPN…")
            self.network.emit(self._net.check_vpn())
            self.progress.emit(15)

            self.status.emit("Генерация аппаратного профиля…")
            hw = self.spoofer.generate_profile(seed=self._session)
            self.profile.emit(hw)
            self.progress.emit(30)

            self.status.emit("Создание JS-расширения…")
            JSInjector().create_extension(hw)
            self.progress.emit(50)

            self.status.emit("Установка расширений CWS…")
            self._ext_mgr.ensure_all()
            self.progress.emit(70)

            self.status.emit("Загрузка / проверка Brave Browser…")
            if not self._brave.ensure_brave():
                self.done.emit(False, "Не удалось загрузить Brave Browser")
                return
            self.progress.emit(100)
            self.done.emit(True, "OK")

        except Exception as e:
            logger.error(f"InitThread: {e}")
            self.done.emit(False, str(e))


# ── Main window ───────────────────────────────────────────────────────────────

class KimShellMainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KimShell  ·  Secure Browser Environment")
        self.setMinimumSize(1050, 700)
        self.setStyleSheet(DARK_THEME)

        self._session    = generate_session_id()
        self._spoofer    = HardwareSpoofer()
        self._brave_mgr  = BraveManager()
        self._cleanup    = CleanupManager()
        self._hw_profile: HardwareProfile | None  = None
        self._brave_proc: subprocess.Popen | None = None
        self._init_thread: InitThread | None      = None

        # logo.svg lives next to main.py (project root)
        self._logo_path = Path(__file__).parent.parent / "logo.svg"

        self._build_ui()
        self._start_init()

    # ─────────────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        hbox = QHBoxLayout(root)
        hbox.setContentsMargins(20, 20, 20, 20)
        hbox.setSpacing(16)

        # ── Left panel ────────────────────────────────────────────────────────
        left = self._card()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(24, 24, 24, 24)
        ll.setSpacing(14)

        # Header row: logo + title
        hdr = QHBoxLayout()
        hdr.setSpacing(12)
        logo_lbl = self._make_logo_label(48)
        hdr.addWidget(logo_lbl)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        t = QLabel("KimShell")
        t.setStyleSheet("font-size:26px; font-weight:bold; color:#00ff88; letter-spacing:3px;")
        s = QLabel(f"Secure Browser Environment  ·  {self._session}")
        s.setStyleSheet("color:#333; font-size:10px; letter-spacing:1px;")
        title_col.addWidget(t)
        title_col.addWidget(s)
        hdr.addLayout(title_col)
        hdr.addStretch()
        ll.addLayout(hdr)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background:#1e1e2e; border:none; max-height:1px;")
        ll.addWidget(div)

        # Network status
        self._net_label = QLabel("🔵  Проверка VPN…")
        self._net_label.setStyleSheet("color:#ffaa00; padding:6px 0; font-size:11px;")
        self._net_label.setWordWrap(True)
        ll.addWidget(self._net_label)

        # Hardware profile info box
        self._profile_label = QLabel("Профиль: генерация…")
        self._profile_label.setStyleSheet(
            "color:#2a4a3a; font-size:10px; font-family:Consolas;"
            "background:#0d0d12; border-radius:6px; padding:8px;"
        )
        self._profile_label.setWordWrap(True)
        ll.addWidget(self._profile_label)

        # Protection settings
        grp = QGroupBox("Параметры защиты")
        gl = QVBoxLayout(grp)
        gl.setSpacing(8)
        self._cb_antifp    = QCheckBox("Антифингерпринтинг (JS-расширение)")
        self._cb_antifp.setChecked(True)
        self._cb_webrtc    = QCheckBox("Блокировка WebRTC")
        self._cb_webrtc.setChecked(True)
        self._cb_cleardata = QCheckBox("Очистка данных при закрытии")
        self._cb_cleardata.setChecked(True)
        for cb in (self._cb_antifp, self._cb_webrtc, self._cb_cleardata):
            gl.addWidget(cb)
        ll.addWidget(grp)

        ll.addStretch()

        # Launch button
        self._btn_launch = QPushButton("🚀  Запустить Brave")
        self._btn_launch.setEnabled(False)
        self._btn_launch.setMinimumHeight(44)
        self._btn_launch.clicked.connect(self._launch_brave)
        ll.addWidget(self._btn_launch)

        # Emergency wipe
        btn_wipe = QPushButton("⛔  Экстренная очистка")
        btn_wipe.setMinimumHeight(38)
        btn_wipe.setStyleSheet(
            "QPushButton{border-color:#ff3366;color:#ff3366;background:#110008;}"
            "QPushButton:hover{background:#ff3366;color:#fff;}"
        )
        btn_wipe.clicked.connect(self._emergency_stop)
        ll.addWidget(btn_wipe)

        # ── Right panel — log with logo watermark ─────────────────────────────
        right = self._card()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 16, 16, 16)
        rl.setSpacing(8)

        log_hdr = QHBoxLayout()
        log_hdr.addWidget(
            QLabel("Системный журнал",
                   styleSheet="color:#333; font-weight:bold; font-size:11px;")
        )
        log_hdr.addStretch()
        log_hdr.addWidget(
            QLabel(f"v{CONFIG.VERSION}",
                   styleSheet="color:#222; font-size:10px; font-family:Consolas;")
        )
        rl.addLayout(log_hdr)

        self._log_view = LogPanel(self._logo_path)
        self._log_view.setStyleSheet(
            "QTextEdit{"
            "  background-color:#0a0a0f; color:#00ff88;"
            "  border:1px solid #1a1a2e; border-radius:8px; padding:8px;"
            "  font-family:Consolas; font-size:11px;"
            "}"
        )
        rl.addWidget(self._log_view)

        # Warn if SVG module not available
        if not _SVG_OK:
            warn = QLabel("⚠ PyQt6-Qt6 не установлен — логотип отключён")
            warn.setStyleSheet("color:#ffaa00; font-size:10px;")
            rl.addWidget(warn)

        # Splitter
        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.addWidget(left)
        sp.addWidget(right)
        sp.setSizes([400, 650])
        hbox.addWidget(sp)

        # Brave process poll
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_brave)
        self._poll_timer.start(2000)

    def _make_logo_label(self, size: int) -> QLabel:
        """Render logo.svg into a fixed-size QLabel."""
        lbl = QLabel()
        lbl.setFixedSize(size, size)
        if _SVG_OK and self._logo_path.is_file():
            r = QSvgRenderer(str(self._logo_path))
            if r.isValid():
                pix = QPixmap(size, size)
                pix.fill(Qt.GlobalColor.transparent)
                p = QPainter(pix)
                r.render(p)
                p.end()
                lbl.setPixmap(pix)
        return lbl

    @staticmethod
    def _card() -> QFrame:
        f = QFrame()
        f.setStyleSheet("background-color:#151520; border-radius:16px;")
        return f

    # ─────────────────────────────────────────────────────────────────────────
    # Init
    # ─────────────────────────────────────────────────────────────────────────

    def _start_init(self) -> None:
        self._loading = LoadingScreen()
        self._loading.start()
        self._loading.show()

        self._init_thread = InitThread(self._session, self._brave_mgr)
        self._init_thread.status.connect(self._log)
        self._init_thread.progress.connect(self._loading.progress.setValue)
        self._init_thread.network.connect(self._on_network)
        self._init_thread.profile.connect(self._on_profile)
        self._init_thread.done.connect(self._on_init_done)
        self._init_thread.start()

    def _on_network(self, s: NetworkStatus) -> None:
        color = "#00ff88" if s.is_vpn_active else "#ff4466"
        icon  = "🟢" if s.is_vpn_active else "🔴"
        self._net_label.setText(f"{icon}  {s.location}  |  {s.isp}\n{s.details}")
        self._net_label.setStyleSheet(f"color:{color}; padding:6px 0; font-size:11px;")

    def _on_profile(self, hw: HardwareProfile) -> None:
        self._hw_profile       = hw
        self._spoofer._profile = hw
        self._profile_label.setText(
            f"CPU   {hw.cpu_model}  ({hw.cpu_cores}c / {hw.cpu_threads}t)\n"
            f"GPU   {hw.gpu_model}\n"
            f"RAM   {hw.total_ram_gb} GB    SCR  {hw.screen_width}×{hw.screen_height}\n"
            f"TZ    {hw.timezone}    LANG  {hw.language}\n"
            f"UA    Chrome/{hw.chrome_version}\n"
            f"HASH  {hw.profile_hash}"
        )
        self._profile_label.setStyleSheet(
            "color:#00bb55; font-size:10px; font-family:Consolas;"
            "background:#0d0d12; border-radius:6px; padding:8px;"
        )

    def _on_init_done(self, ok: bool, msg: str) -> None:
        self._loading.finish()
        if ok:
            self._log(f"✓ Brave: {self._brave_mgr.brave_exe}")
            self._btn_launch.setEnabled(True)
            self._log("✓ Система готова к работе")
        else:
            self._log(f"✗ Ошибка: {msg}")
            QMessageBox.critical(self, "Ошибка инициализации", msg)

    # ─────────────────────────────────────────────────────────────────────────
    # Launch
    # ─────────────────────────────────────────────────────────────────────────

    def _launch_brave(self) -> None:
        try:
            self._log("Запуск Brave Browser…")

            if not self._brave_mgr.brave_exe.is_file():
                raise RuntimeError(
                    f"brave.exe не найден: {self._brave_mgr.brave_exe}\n"
                    "Перезапустите KimShell."
                )

            hw    = self._spoofer.get_profile()
            flags = self._spoofer.to_brave_flags()
            env_v = self._spoofer.to_env_vars()

            if self._cb_antifp.isChecked():
                JSInjector().create_extension(hw)

            if self._cb_webrtc.isChecked():
                f = "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"
                if f not in flags:
                    flags.append(f)

            profile_dir = self._brave_mgr.create_profile(asdict(hw))
            self._cleanup.register(profile_dir)

            cmd = self._brave_mgr.build_command("https://duckduckgo.com", flags)
            self._log(f"EXE : {cmd[0]}")
            self._log(f"DIR : {profile_dir}")

            env = os.environ.copy()
            env.update(env_v)

            self._brave_proc = subprocess.Popen(
                cmd, env=env,
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    | subprocess.BELOW_NORMAL_PRIORITY_CLASS
                ),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            QTimer.singleShot(1200, self._check_alive)

        except Exception as e:
            self._log(f"✗ {e}")
            QMessageBox.critical(self, "Ошибка запуска", str(e))

    def _check_alive(self) -> None:
        """Check ~1.2s after launch whether Brave is still running."""
        if self._brave_proc is None:
            return
        rc = self._brave_proc.poll()   # store once — not called twice
        if rc is not None:
            self._log(f"✗ Brave упал сразу (код {rc})")
            self._brave_proc = None
            self._btn_launch.setText("🚀  Запустить Brave")
        else:
            self._log(f"✓ Brave работает (PID {self._brave_proc.pid})")
            self._btn_launch.setText("🔄  Перезапустить")

    # ─────────────────────────────────────────────────────────────────────────
    # Polling / cleanup
    # ─────────────────────────────────────────────────────────────────────────

    def _poll_brave(self) -> None:
        if self._brave_proc and self._brave_proc.poll() is not None:
            self._log("Brave завершился — очистка профиля…")
            self._brave_mgr.wipe_profile()
            self._brave_proc = None
            self._btn_launch.setText("🚀  Запустить Brave")

    def _kill_our_brave(self) -> None:
        """Kill only the process WE launched — by PID, not by name."""
        if self._brave_proc is None:
            return
        pid = self._brave_proc.pid
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, timeout=5,
            )
            self._log(f"Процесс PID {pid} завершён")
        except Exception as e:
            logger.error(f"taskkill: {e}")

    def _emergency_stop(self) -> None:
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Завершить браузер KimShell и очистить данные сессии?\n"
            "Системный Brave НЕ будет затронут.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._log("⚡ ЭКСТРЕННАЯ ОЧИСТКА")
            self._kill_our_brave()
            self._brave_mgr.wipe_profile()
            self._cleanup.emergency_wipe()
            self._brave_proc = None
            self._btn_launch.setText("🚀  Запустить Brave")

    def _log(self, msg: str) -> None:
        self._log_view.append(f"<span style='color:#1a3a2a'>▸</span> {msg}")
        sb = self._log_view.verticalScrollBar()
        sb.setValue(sb.maximum())
        logger.info(msg)

    # ─────────────────────────────────────────────────────────────────────────
    # Close
    # ─────────────────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._log("Завершение…")
        self._poll_timer.stop()
        self._kill_our_brave()
        if self._brave_proc:
            try:
                self._brave_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._brave_proc.kill()
        self._brave_mgr.full_cleanup()
        self._cleanup.full_cleanup()
        event.accept()
