"""KimShell helper utilities."""

import os
import sys
import random
import string
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Tuple


# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    """Console-only logger."""
    log = logging.getLogger("kimshell")
    log.setLevel(logging.DEBUG)
    for h in log.handlers[:]:
        log.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", "%H:%M:%S")
    handler.setFormatter(fmt)
    log.addHandler(handler)
    return log


logger = setup_logging()


# ── Session ───────────────────────────────────────────────────────────────────

def generate_session_id() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


# ── Secure file wipe ──────────────────────────────────────────────────────────

def secure_wipe(path: Path, passes: int = 3) -> bool:
    """Overwrite file content before deletion."""
    try:
        if not path.exists():
            return True

        if path.is_file():
            size = path.stat().st_size
            if size > 0:
                try:
                    with open(path, "r+b") as f:
                        patterns = [b"\x00", b"\xff", None]
                        for i in range(passes):
                            f.seek(0)
                            pat = patterns[i] if patterns[i] else bytes([random.randint(0, 255)])
                            f.write(pat * size)
                            f.flush()
                            os.fsync(f.fileno())
                except PermissionError:
                    pass
            path.unlink(missing_ok=True)

        elif path.is_dir():
            for item in list(path.rglob("*")):
                if item.is_file():
                    secure_wipe(item, passes=1)
            shutil.rmtree(path, ignore_errors=True)

        return True
    except Exception as e:
        logger.error(f"secure_wipe failed [{path}]: {e}")
        return False


# ── Subprocess ────────────────────────────────────────────────────────────────

def run_command(cmd: list, timeout: int = 60) -> Tuple[bool, str, str]:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)
