r"""Gerenciador de navegador para o NMTBot - modo Chrome real (CDP).

O usuario abre o nmt.gg no Chrome real (onde o Cloudflare ja foi resolvido
manualmente). O bot conecta nesse Chrome via CDP (porta 9222) e atua na
aba selecionada na interface.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import threading
import time
from typing import Callable, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from app.config import APP_DIR, NMT_URL
from app.utils.logger import logger

BROWSER_DATA_DIR = APP_DIR / "browser-data"
CDP_PORT = 9222


class BrowserManager:
    """Gerencia a conexao CDP com o Chrome real do usuario."""

    def __init__(self, headless: bool = False, port: int = CDP_PORT):
        self.headless = headless
        self.port = port
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._running = False
        self._stop_event = asyncio.Event()
        self._on_pages_changed: Optional[Callable[[], None]] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def page(self) -> Optional[Page]:
        return self._page

    def set_on_pages_changed(self, callback: Callable[[], None]) -> None:
        self._on_pages_changed = callback

    # ------------------------------------------------------------------
    # Chrome local
    # ------------------------------------------------------------------
    @staticmethod
    def find_chrome() -> Optional[str]:
        """Localiza o Chrome/Edge instalado no sistema."""
        candidates = [
            shutil.which("chrome"),
            shutil.which("msedge"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        import os
        for p in candidates:
            if p and os.path.exists(p):
                return p
        return None

    def launch_chrome(self, url: str = NMT_URL) -> bool:
        """Abre o Chrome (perfil dedicado do bot) com a porta CDP."""
        exe = self.find_chrome()
        if not exe:
            logger.error("Chrome nao encontrado no sistema.")
            return False
        BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        args = [
            exe,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={BROWSER_DATA_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
            url,
        ]
        logger.info(f"Abrindo Chrome (porta {self.port}): {exe}")
        subprocess.Popen(args)
        return True    # ------------------------------------------------------------------
    # Ciclo de vida CDP
    # ------------------------------------------------------------------
    def connect(self, on_status=None) -> bool:
        """Conecta ao Chrome via CDP (thread + event loop proprios)."""
        if self._thread and self._thread.is_alive():
            return True
        self._running = True
        self._stop_event = asyncio.Event()
        self._thread = threading.Thread(
            target=self._run,
            args=(on_status,),
            daemon=True,
        )
        self._thread.start()

        # Aguarda a conexao CDP ser estabelecida (ate 12s).
        deadline = time.time() + 12
        while time.time() < deadline and self._thread.is_alive() and self._browser is None:
            time.sleep(0.2)
        return self._browser is not None

    def _run(self, on_status) -> None:
        try:
            asyncio.run(self._async_run(on_status))
        except Exception as exc:
            logger.exception(f"Erro no loop CDP: {exc}")
            if on_status:
                on_status(f"Erro: {exc}")
        finally:
            self._running = False

    async def _async_run(self, on_status) -> None:
        self._loop = asyncio.get_running_loop()
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{self.port}"
        )
        if self._browser.contexts:
            self._context = self._browser.contexts[0]
        if on_status:
            on_status(f"Conectado ao Chrome (porta {self.port}).")
        logger.info(f"CDP conectado: {self._browser}")
        try:
            await self._stop_event.wait()
        finally:
            await self._cleanup()

    def stop(self) -> None:
        """Desconecta do Chrome (nao fecha o navegador do usuario)."""
        if self._loop and not self._stop_event.is_set():
            self._loop.call_soon_threadsafe(self._stop_event.set)
        self._running = False

    async def _cleanup(self) -> None:
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._loop = None
    # ------------------------------------------------------------------
    # Abas/paginas abertas
    # ------------------------------------------------------------------
    def list_pages(self) -> list[dict]:
        """Lista as abas abertas: [{index, title, url}, ...]."""
        if self._browser is None or self._loop is None:
            return []
        try:
            return self.run_coro(self._list_pages_coro())
        except Exception as exc:
            logger.warning(f"Falha ao listar abas: {exc}")
            return []

    async def _list_pages_coro(self) -> list[dict]:
        pages = []
        if self._browser is None:
            return pages
        idx = 0
        for ctx in self._browser.contexts:
            for p in ctx.pages:
                try:
                    title = (await p.title()).strip() or "(sem titulo)"
                except Exception:
                    title = "(sem titulo)"
                pages.append({"index": idx, "title": title, "url": p.url})
                idx += 1
        return pages

    def select_page(self, index: int) -> bool:
        """Define a aba ativa pelo indice retornado em list_pages."""
        if self._browser is None or self._loop is None:
            return False
        try:
            return self.run_coro(self._select_page_coro(index))
        except Exception as exc:
            logger.warning(f"Falha ao selecionar aba {index}: {exc}")
            return False

    async def _select_page_coro(self, index: int) -> bool:
        if self._browser is None:
            return False
        idx = 0
        for ctx in self._browser.contexts:
            for p in ctx.pages:
                if idx == index:
                    self._page = p
                    return True
                idx += 1
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def run_coro(self, coro):
        """Agenda coroutine no loop do CDP e devolve o resultado."""
        if not self._loop:
            raise RuntimeError("Chrome nao esta conectado.")
        if not self._browser:
            raise RuntimeError("Chrome nao esta conectado.")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=30)

    def is_alive(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
            and self._browser is not None
        )
