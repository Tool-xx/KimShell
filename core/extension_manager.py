"""
Chrome Web Store extension manager.

How it works:
  - CRX3 is downloaded from Google's update server.
  - CRX3 format: magic(4) + version(4) + header_len(4) + protobuf_header + zip_data
    We skip the binary header and extract the zip portion.
  - Unpacked extension dirs are stored in %APPDATA%/KimShell/cws_extensions/<id>/
  - They are loaded via --load-extension=dir1,dir2,dir3 Brave flag.
  - Version is cached in a .ver file; re-download only when missing.

Extensions bundled by default:
  - ookepigabmicjpgfnmncjiplegcacdbm  (Material Simple Dark Grey theme)
  - gcknhkkoolaabfmlnjonogaaifnjlfnp  (FoxyProxy)
"""

import io
import json
import shutil
import struct
import zipfile
from pathlib import Path
from typing import List, Optional

import requests

from utils.config import CONFIG
from utils.helpers import logger

# Chrome version sent to CWS — must be recent enough to get CRX3
_CHROME_VER = "125.0.6422.112"

_CWS_URL = (
    "https://clients2.google.com/service/update2/crx"
    "?response=redirect"
    f"&prodversion={_CHROME_VER}"
    "&acceptformat=crx3"
    "&x=id%3D{ext_id}%26uc"
)

# Extensions to always install
DEFAULT_EXTENSIONS = [
    ("ookepigabmicjpgfnmncjiplegcacdbm", "Material Dark Grey Theme"),
    ("gcknhkkoolaabfmlnjonogaaifnjlfnp",  "FoxyProxy"),
]


class ExtensionManager:

    def __init__(self) -> None:
        self._base: Path = CONFIG.BASE_DIR / "cws_extensions"
        self._base.mkdir(exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def ensure_all(self) -> List[Path]:
        """
        Download/verify all default extensions.
        Returns list of unpacked extension dirs ready for --load-extension.
        """
        dirs: List[Path] = []
        for ext_id, name in DEFAULT_EXTENSIONS:
            d = self._ensure(ext_id, name)
            if d:
                dirs.append(d)
        return dirs

    def get_load_extension_dirs(self) -> List[Path]:
        """Return cached dirs without re-downloading (for re-launches)."""
        dirs: List[Path] = []
        for ext_id, _ in DEFAULT_EXTENSIONS:
            d = self._ext_dir(ext_id)
            if self._is_valid(d):
                dirs.append(d)
        return dirs

    # ── Internals ─────────────────────────────────────────────────────────────

    def _ext_dir(self, ext_id: str) -> Path:
        return self._base / ext_id

    def _ver_file(self, ext_id: str) -> Path:
        return self._ext_dir(ext_id) / ".ver"

    def _is_valid(self, d: Path) -> bool:
        """Check that extension dir has a manifest.json."""
        return (d / "manifest.json").is_file()

    def _ensure(self, ext_id: str, name: str) -> Optional[Path]:
        d = self._ext_dir(ext_id)
        if self._is_valid(d):
            logger.info(f"Extension cached: {name} ({ext_id[:8]}…)")
            return d
        return self._download(ext_id, name)

    def _download(self, ext_id: str, name: str) -> Optional[Path]:
        url = _CWS_URL.format(ext_id=ext_id)
        logger.info(f"Загрузка расширения: {name}…")
        try:
            r = requests.get(url, timeout=30, allow_redirects=True,
                             headers={"User-Agent": f"Chrome/{_CHROME_VER}"})
            r.raise_for_status()
        except Exception as e:
            logger.error(f"Ошибка загрузки {name}: {e}")
            return None

        raw = r.content
        if not raw:
            logger.error(f"{name}: пустой ответ от CWS")
            return None

        zip_data = self._crx3_to_zip(raw)
        if not zip_data:
            logger.error(f"{name}: не удалось распаковать CRX3")
            return None

        d = self._ext_dir(ext_id)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)

        try:
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                zf.extractall(d)
        except Exception as e:
            logger.error(f"{name}: ошибка распаковки zip: {e}")
            shutil.rmtree(d, ignore_errors=True)
            return None

        if not self._is_valid(d):
            logger.error(f"{name}: manifest.json не найден после распаковки")
            shutil.rmtree(d, ignore_errors=True)
            return None

        # Read version from manifest
        try:
            m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            ver = m.get("version", "?")
        except Exception:
            ver = "?"

        self._ver_file(ext_id).write_text(ver, encoding="utf-8")
        logger.info(f"✓ {name} v{ver} установлен ({ext_id[:8]}…)")
        return d

    @staticmethod
    def _crx3_to_zip(data: bytes) -> Optional[bytes]:
        """
        Strip CRX3 binary header and return raw zip bytes.

        CRX3 layout:
          [0..3]   magic    "Cr24"
          [4..7]   version  \x03\x00\x00\x00
          [8..11]  header_size  (uint32 LE) — length of protobuf header
          [12 .. 12+header_size]  protobuf header (ignored)
          [12+header_size ..]     zip archive
        """
        MAGIC = b"Cr24"
        if len(data) < 12:
            return None

        if data[:4] != MAGIC:
            # Might already be a plain zip (some redirects return zip directly)
            if data[:2] == b"PK":
                return data
            return None

        version = struct.unpack_from("<I", data, 4)[0]
        if version != 3:
            logger.warning(f"CRX version {version} — попытка как zip")
            # Try to find PK signature
            pk = data.find(b"PK")
            return data[pk:] if pk != -1 else None

        header_size = struct.unpack_from("<I", data, 8)[0]
        zip_start   = 12 + header_size

        if zip_start >= len(data):
            return None

        return data[zip_start:]
