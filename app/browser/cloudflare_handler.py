r"""Tratamento de desafios do Cloudflare.

Detecta o intersticial do Cloudflare ("Verificando seu navegador...") e
aguarda a resolução automática, que ocorre em navegadores reais. Se o
desafio persistir (Turnstile interativo), notifica o usuário para
resolução manual.

Não usa serviços de resolução de CAPTCHA — apenas espera e, quando
necessário, pausa para o humano resolver.
"""
from __future__ import annotations

import asyncio
from typing import Callable, Optional

from app.utils.logger import logger

# Sinais do intersticial do Cloudflare
CF_TITLES = ("just a moment", "checking your browser", "verificando seu navegador")
CF_PATH_HINTS = ("/cdn-cgi/challenge",)

# Tempo máximo de espera para resolução automática (segundos)
AUTO_TIMEOUT: float = 45.0
# Tempo extra para desafio interativo/manual (segundos)
MANUAL_TIMEOUT: float = 180.0


async def detect_challenge(page) -> bool:
    """Retorna True se a página está mostrando o desafio do Cloudflare."""
    try:
        url = page.url or ""
        if any(hint in url for hint in CF_PATH_HINTS):
            return True

        title = (await page.title()).strip().lower()
        if any(t in title for t in CF_TITLES):
            return True

        # Elemento característico do Turnstile/intersticial
        try:
            cf_iframe = await page.query_selector('iframe[src*="challenges.cloudflare.com"]')
            if cf_iframe:
                return True
        except Exception:
            pass

        # Spinheiro / texto de verificação
        try:
            body_txt = await page.evaluate("() => document.body ? document.body.innerText.slice(0, 2000) : ''")
            if body_txt:
                bl = body_txt.lower()
                if any(t in bl for t in CF_TITLES):
                    return True
                if "challenge-platform" in bl or "cf-please-wait" in bl:
                    return True
        except Exception:
            pass

    except Exception as exc:
        logger.debug(f"detect_challenge: erro ({exc})")
    return False


async def wait_for_clearance(
    page,
    on_status: Optional[Callable[[str], None]] = None,
    auto_timeout: float = AUTO_TIMEOUT,
    manual_timeout: float = MANUAL_TIMEOUT,
) -> bool:
    """Aguarda o desafio do Cloudflare ser resolvido.

    1. Se não há desafio, retorna imediatamente True.
    2. Aguarda a resolução automática (até auto_timeout).
    3. Se persistir, notifica e aguarda resolução manual (até manual_timeout).
    Retorna True se a página saiu do desafio, False se o tempo expirou.
    """
    emit = on_status or (lambda _m: None)

    if not await detect_challenge(page):
        return True

    emit("Cloudflare: desafio detectado. Aguardando resolução automatica...")
    logger.info("Cloudflare: desafio detectado; aguardando resolucao automatica.")

    # Fase 1: resolução automática
    if await _wait_until_cleared(page, auto_timeout):
        emit("Cloudflare: desafio resolvido automaticamente.")
        logger.info("Cloudflare: desafio resolvido automaticamente.")
        return True

    # Fase 2: desafio interativo — pedir intervenção manual
    emit("Cloudflare: desafio interativo. Resolva manualmente na janela do navegador.")
    logger.warning("Cloudflare: desafio interativo; aguardando resolucao manual.")

    if await _wait_until_cleared(page, manual_timeout):
        emit("Cloudflare: desafio resolvido (manual).")
        logger.info("Cloudflare: desafio resolvido por intervencao manual.")
        return True

    emit("Cloudflare: tempo esgotado aguardando resolucao.")
    logger.error("Cloudflare: tempo esgotado aguardando resolucao.")
    return False


async def _wait_until_cleared(page, timeout: float) -> bool:
    """Espera em polling até a página não mais mostrar o desafio."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            if not await detect_challenge(page):
                # Confirma que chegamos numa página real (URL do jogo)
                return True
        except Exception:
            pass
        await asyncio.sleep(1.0)
    return False