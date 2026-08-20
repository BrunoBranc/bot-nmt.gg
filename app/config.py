r"""Configurações centrais do NMTBot.

Centraliza constantes, URLs e caminhos de arquivos em %APPDATA%\\NMTBot.
"""
from __future__ import annotations

import os
from pathlib import Path


def _appdata_nmtbot() -> Path:
    """Retorna o caminho %APPDATA%\\NMTBot, criando-o se necessário."""
    base = os.environ.get("APPDATA")
    if not base:
        base = os.path.expanduser("~")
    path = Path(base) / "NMTBot"
    path.mkdir(parents=True, exist_ok=True)
    return path


APP_DIR: Path = _appdata_nmtbot()

LICENSE_FILE: Path = APP_DIR / "license.key"
BOT_LOG_FILE: Path = APP_DIR / "bot.log"
WINNERS_LOG_FILE: Path = APP_DIR / "winners.log"

NMT_URL: str = "https://nmt.gg"
POWER_BLOCKS_PLACE_PATH: str = "/api/power-blocks/place"

DEFAULT_BOARD_WIDTH: int = 100
DEFAULT_BOARD_HEIGHT: int = 100

FALLBACK_RADII: tuple[int, ...] = (0, 5, 10, 20, 40, 60)



