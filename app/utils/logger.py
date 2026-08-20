r"""Logging do NMTBot.

Tenta escrever em %APPDATA%\\\NMTBot\\bot.log e winners.log. Se Windows
negar acesso ao diretório, usa logs locais do projeto como fallback.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.config import BOT_LOG_FILE, WINNERS_LOG_FILE


def _safe_log_file(primary: Path, fallback_name: str) -> Path:
    """Retorna arquivo gravável para log, com fallback local."""
    try:
        primary.parent.mkdir(parents=True, exist_ok=True)
        with primary.open("a", encoding="utf-8"):
            pass
        return primary
    except OSError:
        fallback_dir = Path("logs")
        fallback_dir.mkdir(exist_ok=True)
        fallback = fallback_dir / fallback_name
        with fallback.open("a", encoding="utf-8"):
            pass
        return fallback


def _configure() -> logging.Logger:
    """Configura e devolve o logger principal do bot."""
    log = logging.getLogger("NMTBot")
    log.setLevel(logging.INFO)

    if log.handlers:
        return log

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(
        _safe_log_file(BOT_LOG_FILE, "bot.log"),
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    log.addHandler(stream_handler)

    return log


logger: logging.Logger = _configure()

winners_logger: logging.Logger = logging.getLogger("NMTBot.winners")
winners_logger.setLevel(logging.INFO)
if not winners_logger.handlers:
    winners_formatter = logging.Formatter(
        fmt="%(asctime)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    winners_handler = logging.FileHandler(
        _safe_log_file(WINNERS_LOG_FILE, "winners.log"),
        encoding="utf-8",
    )
    winners_handler.setFormatter(winners_formatter)
    winners_logger.addHandler(winners_handler)


def log_winner(message: str) -> None:
    """Registra uma entrada no winners.log."""
    winners_logger.info(message)




