"""KimShell Configuration — Windows only."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class KimShellConfig:
    VERSION: str = "2.0.0"
    APP_NAME: str = "KimShell"

    # Brave — скачивать повторно только если нет исполняемого файла
    BRAVE_FORCE_UPDATE: bool = False
    MAX_FILE_SIZE_MB: int = 100

    VPN_CHECK_SERVERS: List[str] = field(default_factory=lambda: [
        "https://checkip.amazonaws.com",
        "https://api.ipify.org",
    ])

    # ── Директории ──────────────────────────────────────────────────────────
    @property
    def BASE_DIR(self) -> Path:
        p = Path(os.environ.get("APPDATA", Path.home())) / "KimShell"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def CACHE_DIR(self) -> Path:
        p = self.BASE_DIR / "cache"
        p.mkdir(exist_ok=True)
        return p

    @property
    def TEMP_DIR(self) -> Path:
        p = self.BASE_DIR / "temp"
        p.mkdir(exist_ok=True)
        return p

    @property
    def QUARANTINE_DIR(self) -> Path:
        p = self.TEMP_DIR / "quarantine"
        p.mkdir(exist_ok=True)
        return p

    @property
    def BRAVE_DIR(self) -> Path:
        return self.BASE_DIR / "brave_portable"

    @property
    def EXTENSION_DIR(self) -> Path:
        return self.BASE_DIR / "extension"

    @property
    def BRAVE_VERSION_FILE(self) -> Path:
        return self.BRAVE_DIR / ".version"

    def get_session_name(self, uid: str) -> str:
        return f"kimshell_{uid}"


CONFIG = KimShellConfig()
