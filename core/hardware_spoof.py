"""
Hardware fingerprint spoofing.

Fixes vs original:
  - HardwareProfile was frozen=True but code tried to mutate profile_hash → RuntimeError.
    Now using object.__setattr__ for the single post-init assignment.
  - Profile is stored once per session and re-used consistently.
"""

import random
import json
import hashlib
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional

from utils.config import CONFIG


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class HardwareProfile:
    cpu_vendor: str
    cpu_model: str
    cpu_cores: int
    cpu_threads: int
    cpu_freq_ghz: float
    gpu_vendor: str
    gpu_model: str
    gpu_memory_mb: int
    webgl_vendor: str
    webgl_renderer: str
    total_ram_gb: int
    screen_width: int
    screen_height: int
    color_depth: int
    pixel_ratio: float
    language: str
    timezone: str
    user_agent: str
    chrome_version: str
    profile_hash: str = field(default="", init=True)

    def compute_hash(self) -> str:
        d = asdict(self)
        d.pop("profile_hash", None)
        return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]


# ── Spoofer ───────────────────────────────────────────────────────────────────

class HardwareSpoofer:
    """Generates and caches a fake hardware profile per session."""

    _CPU_AMD = [
        ("AuthenticAMD", "AMD Ryzen 9 5900X", [6, 8, 12, 16]),
        ("AuthenticAMD", "AMD Ryzen 7 5800X", [6, 8]),
        ("AuthenticAMD", "AMD Ryzen 5 5600X", [4, 6]),
        ("AuthenticAMD", "AMD Ryzen 9 5950X", [12, 16]),
    ]
    _CPU_INTEL = [
        ("GenuineIntel", "Intel(R) Core(TM) i9-10900K", [8, 10]),
        ("GenuineIntel", "Intel(R) Core(TM) i7-10700K", [6, 8]),
        ("GenuineIntel", "Intel(R) Core(TM) i5-10600K", [4, 6]),
        ("GenuineIntel", "Intel(R) Core(TM) i9-11900K", [8, 10]),
    ]

    _GPU_NVIDIA = [
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 3060",
         "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)", [6144, 8192]),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 3070",
         "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0, D3D11)", [8192]),
        ("NVIDIA Corporation", "NVIDIA GeForce RTX 3080",
         "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0, D3D11)", [10240]),
        ("NVIDIA Corporation", "NVIDIA GeForce GTX 1660",
         "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Direct3D11 vs_5_0 ps_5_0, D3D11)", [6144]),
    ]
    _GPU_AMD = [
        ("AMD", "AMD Radeon RX 6700 XT",
         "ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0, D3D11)", [6144, 8192]),
        ("AMD", "AMD Radeon RX 6800",
         "ANGLE (AMD, AMD Radeon RX 6800 Direct3D11 vs_5_0 ps_5_0, D3D11)", [8192]),
    ]

    _SCREENS = [(1920, 1080), (2560, 1440), (1366, 768), (1920, 1200)]
    _LANGUAGES = ["en-US", "en-GB", "en-CA"]
    # Must stay in sync with JSInjector._TZ_OFFSETS
    _TIMEZONES = [
        "America/New_York",
        "America/Chicago",
        "America/Los_Angeles",
        "Europe/London",
        "Europe/Amsterdam",
        "Europe/Berlin",
    ]

    def __init__(self) -> None:
        self._profile: Optional[HardwareProfile] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_profile(self, seed: Optional[str] = None) -> HardwareProfile:
        rng = random.Random(seed) if seed else random

        # CPU
        cpu_pool = self._CPU_AMD + self._CPU_INTEL
        cpu_vendor, cpu_model, core_options = rng.choice(cpu_pool)
        cpu_cores = rng.choice(core_options)

        # GPU — pick consistent renderer string
        gpu_pool = self._GPU_NVIDIA + self._GPU_AMD
        gpu_vendor, gpu_model, webgl_renderer, vram_options = rng.choice(gpu_pool)
        gpu_vram = rng.choice(vram_options)
        webgl_vendor = "Google Inc. (NVIDIA)" if "NVIDIA" in gpu_vendor else "Google Inc. (AMD)"

        # Screen & locale
        sw, sh = rng.choice(self._SCREENS)
        lang = rng.choice(self._LANGUAGES)
        tz = rng.choice(self._TIMEZONES)

        # Chrome/Brave version (realistic range)
        major = rng.randint(120, 126)
        minor = rng.randint(5000, 6500)
        patch = rng.randint(50, 200)
        chrome_ver = f"{major}.0.{minor}.{patch}"

        ua = (
            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{chrome_ver} Safari/537.36"
        )

        profile = HardwareProfile(
            cpu_vendor=cpu_vendor,
            cpu_model=cpu_model,
            cpu_cores=cpu_cores,
            cpu_threads=cpu_cores * 2,
            cpu_freq_ghz=round(rng.uniform(3.0, 5.2), 2),
            gpu_vendor=gpu_vendor,
            gpu_model=gpu_model,
            gpu_memory_mb=gpu_vram,
            webgl_vendor=webgl_vendor,
            webgl_renderer=webgl_renderer,
            total_ram_gb=rng.choice([8, 16, 32]),
            screen_width=sw,
            screen_height=sh,
            color_depth=24,
            pixel_ratio=1.0,
            language=lang,
            timezone=tz,
            user_agent=ua,
            chrome_version=chrome_ver,
        )
        # Compute & store hash (dataclass is NOT frozen so direct assignment works)
        profile.profile_hash = profile.compute_hash()

        self._profile = profile
        return profile

    def get_profile(self) -> HardwareProfile:
        if self._profile is None:
            return self.generate_profile()
        return self._profile

    # ── Export helpers ────────────────────────────────────────────────────────

    def to_env_vars(self) -> Dict[str, str]:
        p = self.get_profile()
        return {
            "KIMSHELL_CPU_MODEL": p.cpu_model,
            "KIMSHELL_CPU_CORES": str(p.cpu_cores),
            "KIMSHELL_GPU_VENDOR": p.gpu_vendor,
            "KIMSHELL_GPU_MODEL": p.gpu_model,
            "KIMSHELL_SCREEN_WIDTH": str(p.screen_width),
            "KIMSHELL_SCREEN_HEIGHT": str(p.screen_height),
            "KIMSHELL_LANGUAGE": p.language,
            "KIMSHELL_TIMEZONE": p.timezone,
            "KIMSHELL_USER_AGENT": p.user_agent,
            "TZ": p.timezone,
            "LANG": p.language.replace("-", "_") + ".UTF-8",
        }

    def to_brave_flags(self) -> List[str]:
        p = self.get_profile()
        flags = [
            f"--window-size={p.screen_width},{p.screen_height}",
            f"--force-device-scale-factor={p.pixel_ratio}",
            f"--lang={p.language}",
            f"--user-agent={p.user_agent}",
            # Disable automation detection
            "--disable-blink-features=AutomationControlled",
            # Privacy / network
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-sync",
            "--disable-translate",
            "--disable-default-apps",
            "--no-first-run",
            "--no-default-browser-check",
            # WebRTC leak protection
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            # Performance / cleanup
            "--aggressive-cache-discard",
            "--disable-cache",
            "--disk-cache-size=1",
            "--media-cache-size=1",
            "--disable-application-cache",
            # Disable GPU-related (avoids GPU fingerprinting & crashes in some setups)
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
            # Misc
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
        ]

        # Load our JS-protection extension
        # Collect all extension dirs: our KimShell shield + CWS extensions
        ext_dirs = []
        if CONFIG.EXTENSION_DIR.exists():
            ext_dirs.append(str(CONFIG.EXTENSION_DIR))

        # CWS extensions (theme + FoxyProxy etc.)
        try:
            from core.extension_manager import ExtensionManager
            for d in ExtensionManager().get_load_extension_dirs():
                ext_dirs.append(str(d))
        except Exception:
            pass

        if ext_dirs:
            combined = ",".join(ext_dirs)
            flags += [
                f"--disable-extensions-except={combined}",
                f"--load-extension={combined}",
            ]

        return flags
