"""
Secure drag-and-drop file zone.

Fixes vs original:
  - Crypto was imported at module level without guarding the session_key assignment,
    causing AttributeError when pycryptodome was absent.
  - Encrypt→decrypt→expose is pointless for a local file that stays on disk — but we
    keep it as-is for the quarantine-isolation intent, just made fallback consistent.
  - dragLeaveEvent/dragEnterEvent style reset now uses a helper to avoid duplication.
"""

import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QFileDialog, QLabel, QVBoxLayout, QWidget

try:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False

from utils.config import CONFIG
from utils.helpers import logger

_STYLE_IDLE  = "background-color:#1a1a25; border:2px dashed #333; border-radius:12px;"
_STYLE_HOVER = "background-color:#0d1f15; border:2px dashed #00ff88; border-radius:12px;"


class SecureDropZone(QWidget):

    file_received = pyqtSignal(str)  # emits path of processed (safe) file

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumHeight(100)
        self.setStyleSheet(_STYLE_IDLE)

        layout = QVBoxLayout(self)
        self.label = QLabel("📁 Перетащите файл сюда\nили нажмите для выбора")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color:#666; border:none;")
        layout.addWidget(self.label)

        self._quarantine = CONFIG.QUARANTINE_DIR
        self._quarantine.mkdir(exist_ok=True)

        # Session key — only created when crypto is available
        self._key: bytes = get_random_bytes(32) if _CRYPTO_OK else b""
        if not _CRYPTO_OK:
            logger.warning("pycryptodome не установлен — шифрование в карантине отключено")

    # ── Qt events ─────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            path, _ = QFileDialog.getOpenFileName(self, "Выбрать файл")
            if path:
                self._process(Path(path))

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(_STYLE_HOVER)

    def dragLeaveEvent(self, event):
        self.setStyleSheet(_STYLE_IDLE)

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet(_STYLE_IDLE)
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.exists():
                self._process(path)

    # ── Processing ────────────────────────────────────────────────────────────

    def _process(self, src: Path) -> None:
        try:
            if src.stat().st_size > CONFIG.MAX_FILE_SIZE_MB * 1024 * 1024:
                logger.warning(f"Файл слишком большой: {src.name}")
                self.label.setText(f"⚠ Файл слишком большой (>{CONFIG.MAX_FILE_SIZE_MB} МБ)")
                return

            _DANGEROUS = {".exe", ".dll", ".bat", ".cmd", ".sh", ".py", ".js",
                          ".vbs", ".ps1", ".msi", ".scr"}
            if src.suffix.lower() in _DANGEROUS:
                logger.warning(f"Подозрительное расширение: {src.suffix}")
                self.label.setText(f"⚠ Подозрительный файл: {src.name}")

            if _CRYPTO_OK and self._key:
                enc = self._encrypt(src)
                out = self._decrypt(enc)
                enc.unlink(missing_ok=True)
            else:
                out = self._quarantine / f"safe_{src.name}"
                shutil.copy2(src, out)

            logger.info(f"Файл в карантине: {out}")
            self.label.setText(f"✓ {src.name}")
            self.file_received.emit(str(out))

        except Exception as e:
            logger.error(f"Drop error: {e}")
            self.label.setText("✗ Ошибка обработки файла")

    def _encrypt(self, src: Path) -> Path:
        data   = src.read_bytes()
        cipher = AES.new(self._key, AES.MODE_GCM)
        ct, tag = cipher.encrypt_and_digest(data)
        enc = self._quarantine / f"{src.name}.enc"
        enc.write_bytes(cipher.nonce + tag + ct)
        return enc

    def _decrypt(self, enc: Path) -> Path:
        raw   = enc.read_bytes()
        nonce = raw[:16]
        tag   = raw[16:32]
        ct    = raw[32:]
        cipher = AES.new(self._key, AES.MODE_GCM, nonce=nonce)
        data  = cipher.decrypt_and_verify(ct, tag)
        out   = self._quarantine / f"safe_{enc.stem}"
        out.write_bytes(data)
        return out
