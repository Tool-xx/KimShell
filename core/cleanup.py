"""
Cleanup manager — Windows only.

Key fixes:
  - Removed taskkill /IM brave.exe — was killing the user's real Brave browser.
    Process termination is now handled by MainWindow._kill_our_brave() via PID.
  - SIGTERM removed (not valid on Windows).
  - Iterates path list copy to avoid mutation during iteration.
"""

import atexit
import gc
import os
import shutil
import signal
from pathlib import Path
from typing import List

from utils.helpers import logger, secure_wipe
from utils.config import CONFIG


class CleanupManager:

    def __init__(self) -> None:
        self._paths: List[Path] = []
        self._done = False
        atexit.register(self._atexit_cb)
        try:
            signal.signal(signal.SIGINT, self._sigint_cb)
        except (OSError, ValueError):
            pass

    def register(self, path: Path) -> None:
        self._paths.append(path)

    def full_cleanup(self, aggressive: bool = True) -> None:
        if self._done:
            return
        self._done = True
        logger.info("Очистка данных сессии…")

        for path in list(self._paths):
            if not path.exists():
                continue
            try:
                if aggressive and path.is_file():
                    secure_wipe(path, passes=3)
                elif path.is_dir():
                    for f in list(path.rglob("*")):
                        if f.is_file():
                            secure_wipe(f, passes=1)
                    shutil.rmtree(path, ignore_errors=True)
            except Exception as e:
                logger.error(f"Cleanup [{path}]: {e}")

        self._clean_kimshell_temp()
        self._scrub_env()
        gc.collect()
        logger.info("Очистка завершена")

    def emergency_wipe(self) -> None:
        logger.warning("⚡ ЭКСТРЕННАЯ ОЧИСТКА")
        self._done = False
        self.full_cleanup(aggressive=True)

    def _clean_kimshell_temp(self) -> None:
        """Remove only KimShell-created temp dirs — NOT system Brave profile."""
        temp_root = Path(os.environ.get("TEMP", "C:/Windows/Temp"))
        # Only our named patterns
        for pattern in ["kimshell_*"]:
            try:
                for p in temp_root.glob(pattern):
                    shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
            except Exception:
                pass

        # Also clean our own TEMP_DIR
        try:
            td = CONFIG.TEMP_DIR
            for item in list(td.glob("brave_profile_*")):
                shutil.rmtree(item, ignore_errors=True)
        except Exception:
            pass

    def _scrub_env(self) -> None:
        for key in list(os.environ.keys()):
            if any(tag in key for tag in ("KIMSHELL", "SESSION")):
                try:
                    os.environ[key] = "\x00" * 50
                    del os.environ[key]
                except Exception:
                    pass

    def _atexit_cb(self) -> None:
        self.full_cleanup()

    def _sigint_cb(self, signum, frame) -> None:
        self.emergency_wipe()
        raise SystemExit(1)
