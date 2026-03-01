"""
Main window — Windows only.

Key fixes in this version:
  - InitThread now SHARES the same BraveManager instance as MainWindow.
    Previously InitThread created its own BraveManager, downloaded Brave,
    then was discarded — so MainWindow's brave_exe was always empty → "CMD: ."
  - Emergency stop / cleanup kills only OUR process by PID (taskkill /PID),
    not all brave.exe on the system (which wiped the user's real Brave).
  - Added exe existence check before building launch command.
"""

import os
import subprocess
from dataclasses import asdict

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QFrame, QGroupBox, QHBoxLayout,
                             QLabel, QMainWindow, QMessageBox, QPushButton,
                             QSplitter, QTextEdit, QVBoxLayout, QWidget)

from core.brave_manager import BraveManager
from core.cleanup import CleanupManager
from core.hardware_spoof import HardwareProfile, HardwareSpoofer
from core.js_injector import JSInjector
from core.network_checker import NetworkChecker, NetworkStatus
from gui.dnd_widget import SecureDropZone
from gui.loading_screen import LoadingScreen
from gui.styles import DARK_THEME
from utils.helpers import generate_session_id, logger


# ── Background init thread ────────────────────────────────────────────────────

class InitThread(QThread):
    status   = pyqtSignal(str)
    progress = pyqtSignal(int)
    network  = pyqtSignal(object)   # NetworkStatus
    profile  = pyqtSignal(object)   # HardwareProfile
    done     = pyqtSignal(bool, str)

    def __init__(self, session_id: str, brave_mgr: BraveManager) -> None:
        super().__init__()
        self._session = session_id
        self.spoofer  = HardwareSpoofer()
        self._net     = NetworkChecker()
        # Share the SAME BraveManager — so brave_exe is written to the object
        # that MainWindow will use for launch
        self._brave   = brave_mgr

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

        self._session   = generate_session_id()
        self._spoofer   = HardwareSpoofer()
        self._brave_mgr = BraveManager()          # single shared instance
        self._cleanup   = CleanupManager()
        self._hw_profile: HardwareProfile | None  = None
        self._brave_proc: subprocess.Popen | None = None
        self._init_thread: InitThread | None      = None

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

        # Left panel
        left = self._card()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(24, 24, 24, 24)
        ll.setSpacing(12)

        t = QLabel("KimShell")
        t.setStyleSheet("font-size:28px; font-weight:bold; color:#00ff88; letter-spacing:3px;")
        ll.addWidget(t)

        s = QLabel(f"Secure Browser Environment  ·  session {self._session}")
        s.setStyleSheet("color:#444; font-size:10px; letter-spacing:1px;")
        ll.addWidget(s)

        self._net_label = QLabel("🔵 Проверка VPN…")
        self._net_label.setStyleSheet("color:#ffaa00; padding:8px; font-size:11px;")
        self._net_label.setWordWrap(True)
        ll.addWidget(self._net_label)

        self._profile_label = QLabel("Профиль: генерация…")
        self._profile_label.setStyleSheet("color:#555; font-size:11px; font-family:Consolas;")
        self._profile_label.setWordWrap(True)
        ll.addWidget(self._profile_label)

        grp = QGroupBox("Параметры защиты")
        gl = QVBoxLayout(grp)
        self._cb_antifp    = QCheckBox("Антифингерпринтинг (JS-расширение)")
        self._cb_antifp.setChecked(True)
        self._cb_webrtc    = QCheckBox("Блокировка WebRTC")
        self._cb_webrtc.setChecked(True)
        self._cb_cleardata = QCheckBox("Очистка данных при закрытии")
        self._cb_cleardata.setChecked(True)
        for cb in (self._cb_antifp, self._cb_webrtc, self._cb_cleardata):
            gl.addWidget(cb)
        ll.addWidget(grp)

        self._drop = SecureDropZone()
        self._drop.file_received.connect(lambda p: self._log(f"📄 Карантин: {p}"))
        ll.addWidget(self._drop)

        self._btn_launch = QPushButton("🚀  Запустить Brave")
        self._btn_launch.setEnabled(False)
        self._btn_launch.clicked.connect(self._launch_brave)
        ll.addWidget(self._btn_launch)

        btn_wipe = QPushButton("⛔  Экстренная очистка")
        btn_wipe.setStyleSheet("border-color:#ff3366; color:#ff3366;")
        btn_wipe.clicked.connect(self._emergency_stop)
        ll.addWidget(btn_wipe)

        ll.addStretch()

        # Right panel — log
        right = self._card()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 16, 16, 16)
        rl.addWidget(QLabel("Системный журнал",
                            styleSheet="color:#666; font-weight:bold;"))
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        rl.addWidget(self._log_view)

        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.addWidget(left)
        sp.addWidget(right)
        sp.setSizes([410, 640])
        hbox.addWidget(sp)

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_brave)
        self._poll_timer.start(2000)

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

        # Pass self._brave_mgr so the thread populates brave_exe on our object
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
        self._net_label.setStyleSheet(f"color:{color}; padding:8px; font-size:11px;")

    def _on_profile(self, hw: HardwareProfile) -> None:
        self._hw_profile   = hw
        self._spoofer._profile = hw
        self._profile_label.setText(
            f"CPU: {hw.cpu_model} ({hw.cpu_cores}c/{hw.cpu_threads}t)\n"
            f"GPU: {hw.gpu_model}\n"
            f"RAM: {hw.total_ram_gb} ГБ  ·  {hw.screen_width}×{hw.screen_height}\n"
            f"Lang: {hw.language}  ·  TZ: {hw.timezone}\n"
            f"Hash: {hw.profile_hash}"
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

            if not self._brave_mgr.brave_exe.exists():
                raise RuntimeError(
                    f"brave.exe не найден: {self._brave_mgr.brave_exe}\n"
                    "Перезапустите KimShell — Brave скачается заново."
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
                cmd,
                env=env,
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
        if self._brave_proc is None:
            return
        rc = self._brave_proc.poll()
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
            # /T kills the whole process tree (child renderers etc.)
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, timeout=5,
            )
            self._log(f"Процесс PID {pid} завершён")
        except Exception as e:
            logger.error(f"taskkill error: {e}")

    def _emergency_stop(self) -> None:
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Завершить браузер KimShell и очистить данные сессии?\n"
            "Системный Brave на ПК НЕ будет затронут.",
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
        self._log_view.append(f"<span style='color:#555'>▸</span> {msg}")
        self._log_view.verticalScrollBar().setValue(
            self._log_view.verticalScrollBar().maximum()
        )
        logger.info(msg)

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
