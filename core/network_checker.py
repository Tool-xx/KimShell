"""
VPN / proxy detection.

Fixes vs original:
  - ip-api.com was called over plain HTTP → switched to HTTPS.
  - Session timeout was set on the Session object (not supported), fixed to per-request.
  - Risk logic was inverted: VPN present → low risk (good), now correctly labelled.
"""

import re
import requests
from dataclasses import dataclass
from typing import Dict

from utils.helpers import logger
from utils.config import CONFIG


@dataclass
class NetworkStatus:
    is_vpn_active: bool
    public_ip: str
    location: str
    isp: str
    risk_level: str   # "low" = protected, "high" = exposed
    details: str


class NetworkChecker:

    TIMEOUT = 6  # seconds per request

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Mozilla/5.0"

    # ── Public ────────────────────────────────────────────────────────────────

    def check_vpn(self) -> NetworkStatus:
        try:
            public_ip = self._get_public_ip()
            if not public_ip:
                return NetworkStatus(
                    is_vpn_active=False,
                    public_ip="unknown",
                    location="unknown",
                    isp="unknown",
                    risk_level="high",
                    details="Нет подключения к интернету",
                )

            ip_info = self._get_ip_info(public_ip)
            indicators = self._check_vpn_indicators(public_ip)

            org = ip_info.get("org", "").lower()
            vpn_keywords = ["vpn", "proxy", "hosting", "datacenter", "cloud",
                            "digitalocean", "linode", "vultr", "ovh", "hetzner"]
            is_vpn = (
                indicators.get("is_hosting", False)
                or indicators.get("is_proxy", False)
                or any(kw in org for kw in vpn_keywords)
            )

            return NetworkStatus(
                is_vpn_active=is_vpn,
                public_ip=public_ip,
                location=f"{ip_info.get('city', 'Unknown')}, {ip_info.get('country', 'Unknown')}",
                isp=ip_info.get("org", "Unknown"),
                risk_level="low" if is_vpn else "high",
                details="✓ VPN/Proxy обнаружен" if is_vpn else "⚠ Прямое соединение — рекомендуется VPN",
            )

        except Exception as e:
            logger.error(f"Network check error: {e}")
            return NetworkStatus(
                is_vpn_active=False,
                public_ip="error",
                location="error",
                isp="error",
                risk_level="high",
                details=f"Ошибка проверки: {e}",
            )

    # ── Internals ─────────────────────────────────────────────────────────────

    def _get_public_ip(self) -> str:
        for url in CONFIG.VPN_CHECK_SERVERS:
            try:
                r = self.session.get(url, timeout=self.TIMEOUT)
                if r.status_code == 200:
                    ip = r.text.strip()
                    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
                        return ip
            except Exception:
                continue
        return ""

    def _get_ip_info(self, ip: str) -> Dict:
        try:
            r = self.session.get(f"https://ipinfo.io/{ip}/json", timeout=self.TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception:
            return {}

    def _check_vpn_indicators(self, ip: str) -> Dict:
        indicators: Dict = {"is_hosting": False, "is_proxy": False}
        try:
            # FIX: use HTTPS instead of HTTP
            r = self.session.get(
                f"https://ip-api.com/json/{ip}?fields=proxy,hosting,query",
                timeout=self.TIMEOUT,
            )
            data = r.json()
            indicators["is_proxy"]   = bool(data.get("proxy", False))
            indicators["is_hosting"] = bool(data.get("hosting", False))
        except Exception:
            pass
        return indicators
