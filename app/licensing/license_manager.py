"""Licenciamento local/desativado do NMTBot.

Sistema externo de licença removido. Este módulo existe só para
compatibilidade com partes antigas do app e testes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config import LICENSE_FILE


@dataclass
class LicenseStatus:
    valid: bool
    message: str
    raw: Optional[dict] = None


class LicenseManager:
    """Compatibilidade local sem servidor externo."""

    def __init__(self, base_url: str = ""):
        self.base_url = base_url
        self.hwid = "LOCAL"

    def save_key(self, license_key: str) -> None:
        LICENSE_FILE.write_text((license_key or "").strip(), encoding="utf-8")

    def load_saved_key(self) -> Optional[str]:
        if LICENSE_FILE.exists():
            return LICENSE_FILE.read_text(encoding="utf-8").strip()
        return None

    def validate(self, license_key: str = "", is_running: bool = False) -> LicenseStatus:
        return LicenseStatus(valid=True, message="Licenciamento externo removido.")

    def heartbeat(self, license_key: str = "", is_running: bool = True) -> LicenseStatus:
        return LicenseStatus(valid=True, message="Heartbeat externo desativado.")

    def validate_simple(self, license_key: str) -> bool:
        return True

