"""
notifier.py — Notificacoes Telegram para o Bot NMT

Coloque no app/ junto com os outros modulos.
Configure TELEGRAM_TOKEN e TELEGRAM_CHAT_ID em data/settings.json ou
diretamente nas variaveis abaixo.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.utils.logger import logger

# --------------------------------------------------------------------------
# Configuracao — edite aqui ou via settings.json
# --------------------------------------------------------------------------

_SETTINGS_PATH = Path(__file__).parent.parent / "data" / "settings.json"

def _load_telegram_config() -> tuple[Optional[str], Optional[str]]:
    """Le token e chat_id do settings.json."""
    try:
        data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        telegram = data.get("telegram", {})
        return telegram.get("token"), telegram.get("chat_id")
    except Exception:
        return None, None


# --------------------------------------------------------------------------
# Notificador
# --------------------------------------------------------------------------

class TelegramNotifier:
    """Envia mensagens via Telegram Bot API."""

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        cfg_token, cfg_chat_id = _load_telegram_config()
        self.token   = token   or cfg_token
        self.chat_id = chat_id or cfg_chat_id

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, message: str) -> bool:
        """Envia uma mensagem. Retorna True se ok."""
        if not self.enabled:
            logger.debug("Telegram nao configurado — notificacao ignorada.")
            return False
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = json.dumps({
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }).encode()
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                ok = json.loads(r.read()).get("ok", False)
                if ok:
                    logger.info(f"Telegram: mensagem enviada.")
                return ok
        except Exception as e:
            logger.warning(f"Telegram: erro ao enviar mensagem: {e}")
            return False

    def notify_win(
        self,
        round_id: int,
        nmt_won: float,
        figure_name: str,  # usado para passar EXP ganho
        x: int = 0,
        y: int = 0,
    ) -> bool:
        """Notifica uma vitoria no Power Blocks."""
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        exp_part = f"\n⭐ EXP: <b>{figure_name}</b>" if figure_name.startswith("+") else ""
        msg = (
            f"🏆 <b>Vitoria no Power Blocks!</b>\n\n"
            f"🕐 Horario: {now}\n"
            f"🎮 Rodada: <b>#{round_id}</b>\n"
            f"💰 NMT ganho: <b>{nmt_won:.2f} NMT</b>"
            f"{exp_part}"
        )
        return self.send(msg)

    def notify_round_summary(
        self,
        round_id: int,
        figures_placed: int,
        wins: int,
        nmt_total: float,
    ) -> bool:
        """Resumo de uma rodada com multiplas vitorias."""
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        msg = (
            f"🎯 <b>Resumo da Rodada #{round_id}</b>\n\n"
            f"🕐 Horario: {now}\n"
            f"🎴 Figuras colocadas: {figures_placed}\n"
            f"🏆 Celulas vencedoras: {wins}\n"
            f"💰 NMT total: <b>{nmt_total:.4f} NMT</b>"
        )
        return self.send(msg)
