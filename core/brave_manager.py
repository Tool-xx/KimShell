"""
Brave Browser manager — Windows only.

Root cause of "brave_exe = ." bug:
  Path() in Python resolves to "." (current dir), and Path().exists() returns True
  because "." always exists. So exe_ok was always True, ensure_brave() skipped
  download, brave_exe stayed empty, and Popen got "." as executable → WinError 5.

Fix: use .is_file() instead of .exists() for all brave_exe checks.
"""

import json
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

import requests

from utils.config import CONFIG
from utils.helpers import logger, secure_wipe


_UNSET = Path()   # sentinel — means "not found yet"


class BraveManager:

    def __init__(self) -> None:
        self.brave_exe: Path  = _UNSET
        self.profile_dir: Path = _UNSET
        self._locate_existing()

    # ── Locate ────────────────────────────────────────────────────────────────

    def _locate_existing(self) -> None:
        """Scan BRAVE_DIR for brave.exe."""
        if not CONFIG.BRAVE_DIR.exists():
            return
        for p in CONFIG.BRAVE_DIR.rglob("brave.exe"):
            if p.is_file():
                self.brave_exe = p
                logger.info(f"Найден установленный Brave: {p}")
                return

    def _exe_ready(self) -> bool:
        """True only when brave_exe points to an actual file."""
        return self.brave_exe != _UNSET and self.brave_exe.is_file()

    # ── Version helpers ───────────────────────────────────────────────────────

    def get_latest_version(self) -> str:
        try:
            r = requests.get(
                "https://api.github.com/repos/brave/brave-browser/releases/latest",
                timeout=10,
                headers={"Accept": "application/vnd.github+json"},
            )
            r.raise_for_status()
            tag = r.json().get("tag_name", "v1.70.123")
            return tag.lstrip("v")
        except Exception as e:
            logger.warning(f"Не удалось получить версию Brave: {e}")
            return "1.70.123"

    def _cached_version(self) -> str:
        vf = CONFIG.BRAVE_VERSION_FILE
        if vf.is_file():
            return vf.read_text(encoding="utf-8").strip()
        return ""

    def _save_version(self, version: str) -> None:
        CONFIG.BRAVE_VERSION_FILE.write_text(version, encoding="utf-8")

    # ── Ensure Brave is installed ─────────────────────────────────────────────

    def ensure_brave(self, force: bool = False) -> bool:
        """
        Download Brave only when needed.
        Returns True if brave_exe is a real file after the call.
        """
        latest = self.get_latest_version()
        cached = self._cached_version()

        needs_download = (
            not self._exe_ready()                              # exe missing
            or force                                           # forced
            or (CONFIG.BRAVE_FORCE_UPDATE and latest != cached)  # new version
        )

        if not needs_download:
            logger.info(f"Brave уже установлен (v{cached}), загрузка не нужна")
            return True

        ok = self._download(latest)
        if ok:
            # Re-scan after download to populate brave_exe
            self._locate_existing()
        return self._exe_ready()

    def _download(self, version: str) -> bool:
        try:
            brave_dir = CONFIG.BRAVE_DIR
            if brave_dir.exists():
                shutil.rmtree(brave_dir, ignore_errors=True)
            brave_dir.mkdir(parents=True, exist_ok=True)

            url = (
                f"https://github.com/brave/brave-browser/releases/download/"
                f"v{version}/brave-v{version}-win32-x64.zip"
            )
            logger.info(f"Загрузка Brave v{version}…")
            logger.info(f"URL: {url}")

            zip_path = brave_dir / "brave.zip"
            with requests.get(url, stream=True, timeout=300) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                done  = 0
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                            done += len(chunk)
                            if total and done % (5 * 1024 * 1024) < 65536:
                                logger.debug(f"  {done // 1048576} / {total // 1048576} МБ")

            logger.info("Распаковка…")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(brave_dir)
            zip_path.unlink(missing_ok=True)

            # Verify
            found = [p for p in brave_dir.rglob("brave.exe") if p.is_file()]
            if not found:
                logger.error("brave.exe не найден после распаковки")
                return False

            self.brave_exe = found[0]
            self._save_version(version)
            logger.info(f"Brave установлен: {self.brave_exe}")
            return True

        except Exception as e:
            logger.error(f"Ошибка загрузки Brave: {e}")
            return False

    # ── Profile ───────────────────────────────────────────────────────────────

    def create_profile(self, hw: Dict) -> Path:
        profile_id  = uuid.uuid4().hex[:12]
        profile_dir = CONFIG.TEMP_DIR / f"brave_profile_{profile_id}"
        default_dir = profile_dir / "Default"
        default_dir.mkdir(parents=True, exist_ok=True)
        self.profile_dir = profile_dir

        with open(default_dir / "Preferences", "w", encoding="utf-8") as f:
            json.dump(self._build_prefs(hw), f)

        with open(default_dir / "Secure Preferences", "w", encoding="utf-8") as f:
            json.dump({"extensions": {"settings": {}}, "protection": {"macs": {}}}, f)

        return profile_dir

    def _build_prefs(self, hw: Dict) -> Dict:
        return {
            "browser": {
                "window_placement": {
                    "bottom": hw.get("screen_height", 1080),
                    "left": 0,
                    "right": hw.get("screen_width", 1920),
                    "top": 0,
                },
                "clear_data": {
                    "on_exit": {
                        "cache": True, "cookies": True,
                        "form_data": True, "history": True, "passwords": True,
                    }
                },
            },
            "profile": {
                "name": "Default",
                "password_manager_enabled": False,
                "autofill_enabled": False,
            },
            "brave": {
                "shields_settings": {
                    "advanced_view_enabled": True,
                    "default_shields_settings": {
                        "ad_control": "block",
                        "cookie_control": "block_third_party",
                        "fingerprinting_control": "strict",
                        "https_everywhere_enabled": True,
                    },
                },
                "rewards": {"enabled": False},
                "wallet": {"hide_brave_wallet_icon_on_toolbar": True},
            },
            "privacy": {
                "webrtc_ip_handling_policy": "disable_non_proxied_udp",
            },
            "default_search_provider": {
                "enabled": True,
                "name": "DuckDuckGo",
                "search_url": "https://duckduckgo.com/?q={searchTerms}",
            },
        }

    # ── Launch command ────────────────────────────────────────────────────────

    def build_command(self, url: str = "about:blank",
                      extra_flags: Optional[List[str]] = None) -> List[str]:
        if not self._exe_ready():
            raise RuntimeError(
                f"brave.exe не найден (путь: {self.brave_exe}). "
                "Убедитесь что ensure_brave() завершился успешно."
            )

        cmd: List[str] = [str(self.brave_exe)]

        if self.profile_dir.is_dir():
            cmd.append(f"--user-data-dir={self.profile_dir}")

        if extra_flags:
            cmd.extend(f for f in extra_flags if f)

        cmd.append(url)
        return cmd

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def wipe_profile(self) -> None:
        if self.profile_dir.is_dir():
            secure_wipe(self.profile_dir)
            self.profile_dir = _UNSET
            logger.info("Профиль Brave удалён")

    def full_cleanup(self) -> None:
        self.wipe_profile()
        if CONFIG.BRAVE_FORCE_UPDATE and CONFIG.BRAVE_DIR.exists():
            shutil.rmtree(CONFIG.BRAVE_DIR, ignore_errors=True)
            logger.info("Brave удалён (FORCE_UPDATE)")
