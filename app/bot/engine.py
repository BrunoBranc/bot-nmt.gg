r"""Orquestrador principal do bot - API via Chrome fetch() com JWT + Live Ticket via Socket.IO.

Headers obrigatorios confirmados:
  Authorization: Bearer <jwt>
  Idempotency-Key: <uuid-unico-por-request>
  X-NMT-Live-Ticket: <hash recebido via socket.io evento live:ticket>

O ticket e mantido automaticamente por uma conexao Python socket.io permanente.
Quando o servidor emite um novo live:ticket, o bot atualiza sem interrupcao.
"""
from __future__ import annotations

import random
import threading
import time
import uuid
from typing import Callable, Optional

import socketio as sio_lib

from app.bot.humanize import get_humanizer
from app.browser.browser_manager import BrowserManager
from app.config import NMT_URL
from app.notifier import TelegramNotifier
from app.utils.logger import log_winner, logger

CURRENT_PATH = "/api/power-blocks/current"
FIGURES_PATH = "/api/figures?skip=0&take=100"
PLACE_PATH   = "/api/power-blocks/place"

# Extrai JWT do localStorage
_JS_GET_TOKEN = r"""
() => {
    for (const source of ["localStorage", "sessionStorage"]) {
        try {
            const s = window[source];
            for (let i = 0; i < s.length; i++) {
                const key = s.key(i);
                const lower = key.toLowerCase();
                if (!(lower.includes("auth") || lower.includes("supabase") || lower.startsWith("sb-"))) continue;
                try {
                    const p = JSON.parse(s.getItem(key));
                    if (p && p.access_token) return p.access_token;
                    if (p && p.session && p.session.access_token) return p.session.access_token;
                } catch(e) {}
            }
        } catch(e) {}
    }
    return null;
}
"""

# Patch permanente no fetch nativo — captura o ticket de QUALQUER
# POST que o site faca com X-NMT-Live-Ticket (incluindo places manuais
# e os feitos pelo proprio Next.js internamente).
# O ticket fica em window.__nmtLiveTicket e e atualizado automaticamente.
_JS_INSTALL_PATCH = """
() => {
    if (window.__nmtPatchInstalled) return 'already_installed';
    const orig = window.fetch;
    window.__nmtLiveTicket = null;
    window.__nmtPatchInstalled = true;
    window.fetch = function(...args) {
        const [url, opts] = args;
        if (opts?.headers) {
            const h = opts.headers;
            const ticket = h['X-NMT-Live-Ticket'] ||
                (typeof h.get === 'function' ? h.get('X-NMT-Live-Ticket') : null);
            if (ticket) window.__nmtLiveTicket = ticket;
        }
        return orig.apply(this, args);
    };
    return 'installed';
}
"""

# Le o ticket atual capturado pelo patch
_JS_READ_TICKET = "() => window.__nmtLiveTicket || null"

# Verifica se o patch ainda esta ativo (some se a pagina recarregar)
_JS_CHECK_PATCH = "() => !!window.__nmtPatchInstalled"

_JS_FETCH_GET = """
async ([url, token]) => {
    const headers = { "Accept": "application/json" };
    if (token) headers["Authorization"] = "Bearer " + token;
    try {
        const r = await fetch(url, { credentials: "include", headers });
        return { status: r.status, body: await r.text() };
    } catch(e) {
        return { status: 0, body: String(e) };
    }
}
"""

_JS_FETCH_POST = """
async ([url, payload, token, ticket, idempotencyKey]) => {
    const headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    };
    if (token)          headers["Authorization"]   = "Bearer " + token;
    if (ticket)         headers["X-NMT-Live-Ticket"] = ticket;
    if (idempotencyKey) headers["Idempotency-Key"]  = idempotencyKey;
    try {
        const r = await fetch(url, {
            method: "POST",
            credentials: "include",
            headers,
            body: JSON.stringify(payload)
        });
        return { status: r.status, body: await r.text() };
    } catch(e) {
        return { status: 0, body: String(e) };
    }
}
"""

# Clica em uma figura do dock para triggerar o fetch interceptado
# (usado para capturar o ticket automaticamente sem acao manual)
_JS_CLICK_FIGURE_AND_CANCEL = """
async () => {
    // Clica no primeiro botao do dock para abrir o dialogo de place
    const btn = document.querySelector('button.pb-dock__hit, [class*="dock"] button, [class*="figure"] button');
    if (btn) {
        btn.click();
        await new Promise(r => setTimeout(r, 500));
        // Cancela o dialogo de confirmacao (se aparecer)
        const cancel = Array.from(document.querySelectorAll('button')).find(b =>
            b.textContent.trim().toLowerCase() === 'cancel' ||
            b.textContent.trim().toLowerCase() === 'cancelar'
        );
        if (cancel) cancel.click();
    }
    return !!btn;
}
"""


# --------------------------------------------------------------------------
# BrowserAPI
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# TicketManager — mantém o Live Ticket atualizado via Socket.IO Python
# --------------------------------------------------------------------------

class TicketManager:
    """
    Gerencia o Live Ticket via Socket.IO + fallback Chrome.

    Opcao 3: valida o ticket proativamente antes de cada rodada.
             Se invalido, forca reconexao imediata do socket.
    Opcao 4: se o socket nao entregar ticket em 10s, chama x_()
             diretamente no Chrome via page.evaluate() como fallback.
    """

    # JS que chama x_() do modulo webpack para obter o ticket direto do Chrome
    _JS_GET_TICKET_FROM_CHROME = """
    async () => {
        try {
            // Procura o modulo que exporta x_() no cache do webpack
            const cache = window.__webpack_require__?.c || {};
            for (const mod of Object.values(cache)) {
                const x_ = mod?.exports?.x_;
                if (typeof x_ === 'function') {
                    try {
                        const ticket = await x_();
                        if (ticket && typeof ticket === 'string') return ticket;
                    } catch(e) {}
                }
            }
            // Fallback: le do window.__nmtLiveTicket (patch de fetch)
            return window.__nmtLiveTicket || null;
        } catch(e) {
            return null;
        }
    }
    """

    # JS que instala o patch de fetch para capturar ticket passivamente
    _JS_INSTALL_FETCH_PATCH = """
    () => {
        if (window.__nmtPatchInstalled) return 'already';
        const orig = window.fetch;
        window.__nmtLiveTicket = null;
        window.__nmtPatchInstalled = true;
        window.fetch = function(...args) {
            const [url, opts] = args;
            if (opts?.headers) {
                const t = opts.headers['X-NMT-Live-Ticket'] ||
                    (typeof opts.headers.get === 'function'
                        ? opts.headers.get('X-NMT-Live-Ticket') : null);
                if (t) window.__nmtLiveTicket = t;
            }
            return orig.apply(this, args);
        };
        return 'installed';
    }
    """

    def __init__(self, base_url: str,
                 on_log: Optional[Callable[[str], None]] = None,
                 on_win: Optional[Callable[[dict], None]] = None,
                 browser: Optional["BrowserManager"] = None):
        self.base_url  = base_url
        self._log      = on_log or (lambda _: None)
        self._on_win   = on_win
        self._browser  = browser  # referencia ao BrowserManager para fallback Chrome
        self._ticket: Optional[str] = None
        self._token:  Optional[str] = None
        self._sio:    Optional[sio_lib.Client] = None
        self._lock    = threading.Lock()
        self._connected  = False
        self._running    = False
        self._thread: Optional[threading.Thread] = None
        self._last_ticket_time: float = 0.0  # quando o ultimo ticket chegou

    def set_token(self, token: str) -> None:
        self._token = token

    def get_ticket(self) -> Optional[str]:
        with self._lock:
            return self._ticket

    def clear_ticket(self) -> None:
        with self._lock:
            self._ticket = None
            self._last_ticket_time = 0.0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._connect_loop, daemon=True)
        self._thread.start()
        # Instala o patch de fetch no Chrome em background
        threading.Thread(target=self._install_fetch_patch, daemon=True).start()

    def stop(self) -> None:
        self._running = False
        try:
            if self._sio and self._connected:
                self._sio.disconnect()
        except Exception:
            pass

    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Opcao 3: Validacao proativa do ticket
    # ------------------------------------------------------------------

    def ensure_valid_ticket(self, timeout: float = 30.0) -> Optional[str]:
        """
        Garante que temos um ticket valido antes de cada rodada.
        1. Se temos ticket e socket conectado → retorna direto.
        2. Se socket desconectado → forca reconexao e aguarda.
        3. Se ainda sem ticket → usa fallback Chrome (opcao 4).
        """
        ticket = self.get_ticket()

        # Ticket disponivel e socket ok → retorna direto
        if ticket and self._connected:
            return ticket

        # Socket caiu mas temos ticket recente (< 5 min) → pode ainda ser valido
        if ticket and (time.time() - self._last_ticket_time) < 300:
            self._log("[Ticket] Usando ultimo ticket (socket reconectando)...")
            return ticket

        # Sem ticket ou muito antigo → aguarda reconexao + fallback Chrome
        if not self._connected:
            self._log("[Ticket] Socket desconectado. Aguardando reconexao...")

        return self.wait_for_ticket(timeout)

    # ------------------------------------------------------------------
    # Opcao 4: Fallback via Chrome (x_() do webpack)
    # ------------------------------------------------------------------

    def _get_ticket_from_chrome(self) -> Optional[str]:
        """Chama x_() diretamente no Chrome via page.evaluate()."""
        if not self._browser:
            return None
        try:
            page = self._browser.page
            if not page:
                return None
            ticket = self._browser.run_coro(
                page.evaluate(self._JS_GET_TICKET_FROM_CHROME)
            )
            if ticket:
                self._log(f"[Ticket] Obtido via Chrome fallback ({ticket[:12]}...).")
                with self._lock:
                    self._ticket = ticket
                    self._last_ticket_time = time.time()
            return ticket
        except Exception as e:
            self._log(f"[Ticket] Erro no fallback Chrome: {e}")
            return None

    def _install_fetch_patch(self) -> None:
        """Instala o patch de fetch no Chrome para captura passiva de ticket."""
        if not self._browser:
            return
        try:
            page = self._browser.page
            if page:
                self._browser.run_coro(page.evaluate(self._JS_INSTALL_FETCH_PATCH))
        except Exception:
            pass

    def wait_for_ticket(self, timeout: float = 30.0) -> Optional[str]:
        """
        Aguarda ticket do socket.io. Se nao chegar em 10s,
        tenta o fallback Chrome (opcao 4). Repete ate timeout.
        """
        deadline = time.time() + timeout
        chrome_tried = False

        while time.time() < deadline:
            ticket = self.get_ticket()
            if ticket:
                return ticket

            # Apos 10s sem ticket, tenta o Chrome
            if not chrome_tried and (time.time() - (deadline - timeout)) > 10:
                chrome_tried = True
                self._log("[Ticket] Socket lento — tentando Chrome fallback...")
                ticket = self._get_ticket_from_chrome()
                if ticket:
                    return ticket

            time.sleep(0.5)

        # Ultima tentativa: Chrome
        return self._get_ticket_from_chrome()

    # ------------------------------------------------------------------
    # Loop de conexao Socket.IO
    # ------------------------------------------------------------------

    def _connect_loop(self) -> None:
        retry_delay = 5.0
        while self._running:
            try:
                self._connect_once()
                retry_delay = 5.0  # reset apos conexao bem sucedida
            except Exception as e:
                self._log(f"[SocketIO] Erro: {e}. Reconectando em {retry_delay:.0f}s...")
            if self._running:
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 60.0)  # backoff ate 60s

    def _connect_once(self) -> None:
        if not self._token:
            self._log("[SocketIO] Token nao disponivel. Aguardando...")
            time.sleep(5)
            return

        client = sio_lib.Client(logger=False, engineio_logger=False,
                                reconnection=False)
        self._sio = client

        @client.event
        def connect():
            self._connected = True
            self._log("[SocketIO] Conectado ao nmt.gg.")
            try:
                client.emit("live:request-ticket")
            except Exception:
                pass

        @client.event
        def disconnect():
            self._connected = False
            self._log("[SocketIO] Desconectado. Mantendo ultimo ticket.")

        @client.on("live:ticket")
        def on_ticket(data):
            ticket = None
            if isinstance(data, dict):
                ticket = data.get("ticket")
            elif isinstance(data, str):
                ticket = data
            if ticket:
                with self._lock:
                    self._ticket = ticket
                    self._last_ticket_time = time.time()
                self._log(f"[SocketIO] Ticket recebido ({ticket[:12]}...).")

        @client.on("pb-user-settled")
        def on_pb_user_settled(data):
            if self._on_win and isinstance(data, dict):
                self._on_win({"type": "pb-user-settled", **data})

        @client.on("notification")
        def on_notification(data):
            if not self._on_win or not isinstance(data, dict):
                return
            notif = data.get("notification", {})
            if notif.get("type") == "POWERBLOCK_WIN":
                self._on_win({"type": "notification", **notif})

        client.connect(
            self.base_url,
            socketio_path="/socket.io",
            transports=["websocket", "polling"],
            auth={"token": self._token},
            wait_timeout=15,
        )
        while self._running and self._connected:
            time.sleep(1)
        client.disconnect()


class BrowserAPI:
    def __init__(self, browser: BrowserManager, base_url: str):
        self.browser = browser
        self.base_url = base_url.rstrip("/")
        self._token: Optional[str] = None
        self._ticket: Optional[str] = None

    # --- Token JWT ---

    def refresh_token(self) -> bool:
        try:
            token = self.browser.run_coro(
                self.browser.page.evaluate(_JS_GET_TOKEN)
            )
            if token:
                self._token = token
                logger.info(f"Token JWT extraido ({token[:20]}...).")
                return True
            logger.warning("Nenhum token JWT encontrado.")
            return False
        except Exception as e:
            logger.warning(f"Erro ao extrair token: {e}")
            return False

    # --- Live Ticket ---

    def install_permanent_interceptor(self) -> bool:
        """Instala o patch no fetch nativo. Chama uma vez ao iniciar e re-instala se necessario."""
        try:
            page = self.browser.page
            if not page:
                return False
            result = self.browser.run_coro(page.evaluate(_JS_INSTALL_PATCH))
            logger.info(f"Patch de ticket: {result}")
            return True
        except Exception as e:
            logger.warning(f"Erro ao instalar patch: {e}")
            return False

    def _ensure_patch(self) -> None:
        """Reinstala o patch se a pagina foi recarregada."""
        try:
            page = self.browser.page
            if not page:
                return
            active = self.browser.run_coro(page.evaluate(_JS_CHECK_PATCH))
            if not active:
                logger.info("Patch inativo (pagina recarregada). Reinstalando...")
                self.browser.run_coro(page.evaluate(_JS_INSTALL_PATCH))
        except Exception as e:
            logger.warning(f"Erro ao verificar patch: {e}")

    def has_ticket(self) -> bool:
        return bool(self.get_ticket())

    def get_ticket(self) -> Optional[str]:
        """Le window.__nmtLiveTicket do browser (capturado pelo patch)."""
        self._ensure_patch()
        try:
            page = self.browser.page
            if not page:
                return self._ticket
            ticket = self.browser.run_coro(page.evaluate(_JS_READ_TICKET))
            if ticket:
                self._ticket = ticket
            return self._ticket
        except Exception:
            return self._ticket

    def clear_ticket(self) -> None:
        self._ticket = None
        try:
            page = self.browser.page
            if page:
                self.browser.run_coro(page.evaluate(
                    "() => { window.__nmtLiveTicket = null; }"
                ))
        except Exception:
            pass

    def capture_ticket_via_intercept(self, timeout: float = 120.0) -> Optional[str]:
        """Aguarda window.__nmtLiveTicket ser preenchido pelo patch."""
        self._ensure_patch()
        deadline = time.time() + timeout
        while time.time() < deadline:
            ticket = self.get_ticket()
            if ticket:
                return ticket
            time.sleep(1.0)
        return None

    # --- GET / POST ---

    def get(self, path: str) -> tuple[int, Optional[dict]]:
        try:
            return self.browser.run_coro(self._get(path))
        except Exception as e:
            logger.warning(f"BrowserAPI.get {path}: {e}")
            return 0, None

    def post(self, path: str, payload: dict, ticket: Optional[str] = None) -> tuple[int, Optional[dict]]:
        idempotency_key = str(uuid.uuid4())
        current_ticket = ticket or self._ticket
        try:
            return self.browser.run_coro(
                self._post(path, payload, idempotency_key, current_ticket)
            )
        except Exception as e:
            logger.warning(f"BrowserAPI.post {path}: {e}")
            return 0, None

    async def _get(self, path: str) -> tuple[int, Optional[dict]]:
        import json
        page = self.browser.page
        if not page:
            return 0, None
        result = await page.evaluate(_JS_FETCH_GET, [self.base_url + path, self._token])
        return self._parse(result)

    async def _post(self, path: str, payload: dict, idempotency_key: str, ticket: Optional[str] = None) -> tuple[int, Optional[dict]]:
        import json
        page = self.browser.page
        if not page:
            return 0, None
        result = await page.evaluate(
            _JS_FETCH_POST,
            [self.base_url + path, payload, self._token, ticket, idempotency_key]
        )
        return self._parse(result)

    @staticmethod
    def _parse(result: dict) -> tuple[int, Optional[dict]]:
        import json
        status = result.get("status", 0)
        try:
            return status, json.loads(result.get("body", ""))
        except Exception:
            return status, None


# --------------------------------------------------------------------------
# Posicionamento
# --------------------------------------------------------------------------

def _occupied_cells(current: dict) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for p in current.get("placements", []):
        x, y = p.get("x"), p.get("y")
        if x is None or y is None:
            continue
        side = int(p.get("side") or 1)
        for dx in range(side):
            for dy in range(side):
                cells.add((int(x) + dx, int(y) + dy))
    return cells


def _find_free(
    occupied: set[tuple[int, int]],
    used: set[tuple[int, int]],
    board_size: int,
    rng: random.Random,
) -> Optional[tuple[int, int]]:
    all_taken = occupied | used
    for _ in range(500):
        x = rng.randint(0, board_size - 1)
        y = rng.randint(0, board_size - 1)
        if (x, y) not in all_taken:
            return x, y
    for x in range(board_size):
        for y in range(board_size):
            if (x, y) not in all_taken:
                return x, y
    return None


# --------------------------------------------------------------------------
# BotEngine
# --------------------------------------------------------------------------

class BotEngine:
    def __init__(
        self,
        headless: bool = False,
        url: str = NMT_URL,
        loop_interval: float = 5.0,
        poll_interval: float = 3.0,
        max_figures_per_round: int = 10,
        on_status: Optional[Callable[[str], None]] = None,
    ):
        self.headless = headless
        self.url = url
        self.loop_interval = max(1.0, loop_interval)
        self.poll_interval = max(0.5, poll_interval)
        self.max_figures_per_round = max(1, max_figures_per_round)
        self.on_status = on_status or (lambda _: None)

        self.browser = BrowserManager(headless=headless)
        self._humanizer = get_humanizer()
        self._rng = random.Random()
        self._api: Optional[BrowserAPI] = None
        self._ticket_mgr: Optional[TicketManager] = None
        self._notifier = TelegramNotifier()

        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()
        self._browser_open = False
        self._opening_browser = False
        self._tab_selected = False
        self._on_browser_ready_callback: Optional[Callable[[], None]] = None

        self._stats_lock = threading.Lock()
        self._stats: dict = {
            "figures_placed": 0,
            "rounds_seen": 0,
            "rounds_processed": 0,
            "errors": 0,
            "start_time": 0.0,
            "current_round": "-",
            "current_timer": 0,
            "last_action_time": 0.0,
            "nmt_total": 0.0,
            "nmt_wins": 0,
            "nmt_last": "-",
        }
        self._on_stats_callback: Optional[Callable[[dict], None]] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def browser_ready(self) -> bool:
        return self._browser_open and self._tab_selected

    @property
    def stats(self) -> dict:
        with self._stats_lock:
            d = dict(self._stats)
        d["uptime"] = time.time() - d["start_time"] if d.get("start_time") else 0
        return d

    def set_on_stats(self, cb): self._on_stats_callback = cb
    def set_on_browser_ready(self, cb): self._on_browser_ready_callback = cb

    _COUNTER_KEYS = {"figures_placed", "errors", "rounds_seen", "rounds_processed", "nmt_wins", "nmt_total"}

    def _update_stat(self, key: str, value) -> None:
        with self._stats_lock:
            if key in self._COUNTER_KEYS:
                self._stats[key] = self._stats.get(key, 0) + value
            else:
                self._stats[key] = value
        if self._on_stats_callback:
            try: self._on_stats_callback(self.stats)
            except Exception: pass

    # ------------------------------------------------------------------
    # Fase 1: Navegador
    # ------------------------------------------------------------------

    def open_browser(self) -> None:
        if self._browser_open or self._opening_browser or self.browser.is_alive():
            self._emit("Navegador ja esta conectado.")
            return
        self._opening_browser = True
        threading.Thread(target=self._open_browser_worker, daemon=True).start()

    def _open_browser_worker(self) -> None:
        try:
            if not self.browser.launch_chrome(self.url):
                self._emit("Chrome nao encontrado. Instale o Google Chrome.")
                return
            self._emit("Abrindo Chrome... Resolva o Cloudflare/login na janela.")
            if not self.browser.connect(on_status=lambda m: self._emit(m)):
                raise RuntimeError("Nao foi possivel conectar ao Chrome via CDP.")
            self._browser_open = True
            self._emit("Chrome conectado. Selecione a aba na interface.")
            if self._on_browser_ready_callback:
                try: self._on_browser_ready_callback()
                except Exception: pass
        except Exception as exc:
            logger.exception(f"Erro ao abrir navegador: {exc}")
            self._emit(f"Erro ao abrir navegador: {exc}")
        finally:
            self._opening_browser = False

    def list_tabs(self) -> list[dict]:
        return self.browser.list_pages() if self.browser.is_alive() else []

    def select_tab(self, index: int) -> bool:
        if not self.browser.is_alive():
            self._emit("Chrome nao esta conectado.")
            return False
        ok = self.browser.select_page(index)
        self._tab_selected = ok
        self._emit(
            f"Aba {index} selecionada. Clique em Iniciar bot."
            if ok else "Falha ao selecionar a aba."
        )
        return ok

    # ------------------------------------------------------------------
    # Fase 2: Automacao
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        if not self.browser_ready:
            self._emit("Chrome nao esta pronto. Abra e selecione a aba.")
            return
        self._stop_event.clear()
        self._running = True
        self._update_stat("start_time", time.time())
        self._thread = threading.Thread(target=self._run_automation, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        self.browser.stop()
        if self._thread:
            self._thread.join(timeout=10)
        self._browser_open = False
        self._opening_browser = False
        self._tab_selected = False

    def _run_automation(self) -> None:
        try:
            self._api = BrowserAPI(self.browser, self.url)
            if not self._api.refresh_token():
                self._emit("Nao foi possivel extrair o token JWT. Verifique o login.")
                return

            # Inicia o TicketManager via socket.io Python
            self._ticket_mgr = TicketManager(
                base_url=self.url,
                on_log=lambda msg: self._emit(msg),
                on_win=self._on_socket_win,
                browser=self.browser,
            )
            self._ticket_mgr.set_token(self._api._token)
            self._ticket_mgr.start()
            self._emit("Conectando ao socket.io para renovacao automatica de ticket...")

            # Aguarda o primeiro ticket chegar (max 20s)
            ticket = self._ticket_mgr.wait_for_ticket(timeout=20.0)
            if ticket:
                self._emit(f"Ticket inicial recebido ({ticket[:12]}...).")
            else:
                self._emit("Ticket nao chegou em 20s — continuando mesmo assim.")

            self._run_loop()
        except Exception as exc:
            logger.exception(f"Erro fatal: {exc}")
            self._emit(f"Erro fatal: {exc}")
        finally:
            if self._ticket_mgr:
                self._ticket_mgr.stop()
            self._running = False
            self._emit("Bot encerrado.")

    # ------------------------------------------------------------------
    # Loop principal
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        self._emit("Loop iniciado (Chrome fetch + JWT + Live Ticket)...")

        last_round_id: Optional[int] = None
        last_action_round: Optional[int] = None
        consecutive_errors = 0

        while self._running and not self._stop_event.is_set():

            status, current = self._api.get(CURRENT_PATH)

            if status == 0 or current is None:
                consecutive_errors += 1
                self._emit(f"Sem resposta da API ({consecutive_errors}x). Aguardando...")
                self._update_stat("errors", 1)
                self._sleep(self.poll_interval * 2)
                continue

            if status in (401, 403):
                self._emit(f"HTTP {status} — renovando token...")
                self._api.refresh_token()
                # Atualiza token no TicketManager e reconecta socket
                if self._ticket_mgr and self._api._token:
                    self._ticket_mgr.set_token(self._api._token)
                self._sleep(3)
                continue

            consecutive_errors = 0
            round_id   = current.get("id")
            status_str = current.get("status", "")
            board_size = int(current.get("boardSize") or 120)
            ends_in    = int(current.get("endsInSeconds") or 0)

            self._update_stat("current_round", str(round_id))
            self._update_stat("current_timer", ends_in)

            if status_str != "ACTIVE":
                self._emit(f"Rodada {round_id} nao ativa (status={status_str}). Aguardando...")
                self._sleep(self.poll_interval)
                continue

            round_changed = (round_id != last_round_id and last_round_id is not None)
            if round_changed:
                self._update_stat("rounds_seen", 1)
                self._emit(f"Nova rodada: {round_id} | boardSize={board_size} | {ends_in}s restantes")
                self._humanizer.sleep_round()
            elif last_round_id is None:
                self._emit(f"Rodada inicial: {round_id} | boardSize={board_size} | {ends_in}s restantes")

            if round_id != last_action_round:
                if ends_in < 8:
                    self._emit(f"Tempo restante muito curto ({ends_in}s), pulando.")
                else:
                    # Opcao 3+4: valida ticket proativamente antes de cada rodada
                    ticket = self._ticket_mgr.ensure_valid_ticket(timeout=30.0) if self._ticket_mgr else None
                    if not ticket:
                        self._emit("Sem ticket valido. Pulando rodada...")
                        last_action_round = round_id
                        self._sleep(self.poll_interval)
                        continue

                    occupied = _occupied_cells(current)
                    self._emit(f"Celulas ocupadas: {len(occupied)} | Colocando figuras...")
                    placed = self._place_figures(round_id, board_size, occupied)
                    self._update_stat("rounds_processed", 1)
                    self._update_stat("last_action_time", time.time())
                    if placed:
                        self._update_stat("figures_placed", placed)
                        self._emit(f"Rodada {round_id}: {placed} figura(s) colocada(s).")
                    else:
                        self._emit(f"Rodada {round_id}: nenhuma figura colocada.")
                last_action_round = round_id

            last_round_id = round_id
            self._humanizer.sleep_base()
            self._sleep(self.poll_interval)

        self._emit("Loop finalizado.")

    # ------------------------------------------------------------------
    # Captura do Live Ticket
    # ------------------------------------------------------------------

    def _acquire_ticket(self) -> bool:
        """
        Garante um ticket valido usando opcoes 3 e 4:
        - Opcao 3: valida proativamente, forca reconexao se necessario
        - Opcao 4: fallback direto via Chrome se socket lento/falho
        """
        ticket = self._ticket_mgr.ensure_valid_ticket(timeout=60.0) if self._ticket_mgr else None
        if ticket:
            return True
        self._emit("Nao foi possivel obter ticket. Verifique a conexao.")
        return False

    def _on_socket_win(self, data: dict) -> None:
        """Chamado pelo TicketManager quando o usuario ganhou NMT."""
        try:
            event_type = data.get("type", "")

            if event_type == "pb-user-settled":
                # { roundId, reward, exp, boxes }
                round_id  = data.get("roundId", "?")
                nmt_won   = float(data.get("reward", 0))
                exp       = data.get("exp", 0)
                if nmt_won <= 0:
                    return
                from datetime import datetime
                last_str = f"+{nmt_won:.2f} NMT ({datetime.now().strftime('%H:%M')})"
                self._update_stat("nmt_total", nmt_won)
                self._update_stat("nmt_wins", 1)
                self._update_stat("nmt_last", last_str)
                msg = f"🏆 VITORIA! Rodada #{round_id} — {nmt_won:.2f} NMT + {exp} EXP"
                self._emit(msg)
                if self._notifier.enabled:
                    self._notifier.notify_win(
                        round_id=int(round_id),
                        nmt_won=nmt_won,
                        figure_name=f"+{exp} EXP",
                        x=0, y=0,
                    )

            elif event_type == "notification":
                # Fallback via notificacao do servidor
                meta     = data.get("meta", {})
                round_id = meta.get("roundId", "?")
                nmt_won  = float(meta.get("reward", 0))
                exp      = meta.get("exp", 0)
                if nmt_won <= 0:
                    return
                from datetime import datetime
                last_str = f"+{nmt_won:.2f} NMT ({datetime.now().strftime('%H:%M')})"
                self._update_stat("nmt_total", nmt_won)
                self._update_stat("nmt_wins", 1)
                self._update_stat("nmt_last", last_str)
                msg = f"🏆 VITORIA! Rodada #{round_id} — {nmt_won:.2f} NMT + {exp} EXP"
                self._emit(msg)
                if self._notifier.enabled:
                    self._notifier.notify_win(
                        round_id=int(round_id),
                        nmt_won=nmt_won,
                        figure_name=f"+{exp} EXP",
                        x=0, y=0,
                    )
        except Exception as e:
            logger.warning(f"Erro ao processar evento de vitoria: {e}")

    def _capture_ticket_via_auto_place(self) -> bool:
        # Nao e mais necessario — o TicketManager cuida disso via socket.io
        return False

    # ------------------------------------------------------------------
    # Colocacao de figuras
    # ------------------------------------------------------------------

    def _place_figures(self, round_id: int, board_size: int, occupied: set) -> int:
        fig_status, figures_resp = self._api.get(FIGURES_PATH)

        if fig_status in (401, 403):
            self._emit(f"  Token expirado (HTTP {fig_status}). Renovando...")
            self._api.refresh_token()
            fig_status, figures_resp = self._api.get(FIGURES_PATH)

        if not figures_resp or not isinstance(figures_resp, dict):
            self._emit(f"  Erro ao buscar figuras (HTTP {fig_status}).")
            return 0

        all_items = figures_resp.get("items", [])
        # Filtra figuras disponíveis para jogar: IDLE ou LOCKED, com power > 0
        PLAYABLE_STATES = {"IDLE", "LOCKED"}
        idle = [f for f in all_items if f.get("state") in PLAYABLE_STATES and (f.get("power") or 0) > 0]

        if not idle:
            placed_count = len([f for f in all_items if f.get("state") != "IDLE"])
            self._emit(
                f"  Nenhuma figura IDLE. Total: {len(all_items)}"
                + (f" ({placed_count} ja colocadas)." if placed_count else ".")
            )
            return 0

        to_place = idle[: self.max_figures_per_round]
        self._emit(f"  Figuras IDLE: {len(idle)} | Colocando: {len(to_place)}")

        placed = 0
        used: set[tuple[int, int]] = set()

        for item in to_place:
            if not self._running:
                break

            figure_id   = item.get("id")
            figure_name = item.get("name", "?")
            power       = item.get("power", 0)
            if not figure_id:
                continue

            pos = _find_free(occupied, used, board_size, self._rng)
            if pos is None:
                self._emit("  Tabuleiro lotado.")
                break

            x, y = pos
            self._humanizer.sleep_click()

            # Pega o ticket mais recente do TicketManager antes de cada place
            current_ticket = self._ticket_mgr.get_ticket() if self._ticket_mgr else None

            http_status, resp = self._api.post(
                PLACE_PATH, {"figureId": figure_id, "x": x, "y": y},
                ticket=current_ticket
            )

            if 200 <= http_status < 300:
                placed += 1
                used.add((x, y))
                log_winner(
                    f"rodada={round_id} figura={figure_name} "
                    f"id={figure_id} x={x} y={y} power={power}"
                )
                self._emit(f"  [{placed}] {figure_name} (power={power}) -> ({x},{y}) ✓")

                # Verifica se esta figura ganhou NMT (resposta contem rewardPerHit)
                if isinstance(resp, dict):
                    reward_per_hit = resp.get("rewardPerHit") or 0
                    power_spent    = resp.get("powerSpent") or 0
                    if reward_per_hit and power_spent:
                        nmt_won = reward_per_hit * power_spent / 1000
                        from datetime import datetime
                        last_str = f"+{nmt_won:.4f} NMT ({datetime.now().strftime('%H:%M')})"
                        self._update_stat("nmt_total", nmt_won)
                        self._update_stat("nmt_wins", 1)
                        self._update_stat("nmt_last", last_str)
                        self._emit(f"  🏆 VITORIA! {figure_name} ganhou ~{nmt_won:.4f} NMT na rodada {round_id}!")
                        if self._notifier.enabled:
                            self._notifier.notify_win(
                                round_id=round_id,
                                nmt_won=nmt_won,
                                figure_name=figure_name,
                                x=x, y=y,
                            )

            elif http_status == 403:
                msg = ""
                if isinstance(resp, dict):
                    err = resp.get("error", {})
                    msg = err.get("message", str(resp)) if isinstance(err, dict) else str(err)
                self._emit(f"  HTTP 403: {msg}")
                if "ticket" in msg.lower() or "live" in msg.lower() or not msg:
                    self._emit("  Ticket expirou. Aguardando novo ticket do socket.io...")
                    # Nao limpa o ticket — mantém o ultimo até o servidor enviar novo
                    if self._acquire_ticket():
                        return self._place_figures(round_id, board_size, occupied)
                break

            elif http_status == 400:
                msg = ""
                if isinstance(resp, dict):
                    err = resp.get("error", {})
                    msg = err.get("message", "") if isinstance(err, dict) else str(resp)
                self._emit(f"  {figure_name} em ({x},{y}): HTTP 400 — {msg}. Tentando outras posicoes...")
                used.add((x, y))
                success = False
                for attempt in range(5):
                    pos_r = _find_free(occupied, used, board_size, self._rng)
                    if not pos_r:
                        break
                    xr, yr = pos_r
                    http_r, _ = self._api.post(PLACE_PATH, {"figureId": figure_id, "x": xr, "y": yr}, ticket=current_ticket)
                    if 200 <= http_r < 300:
                        placed += 1
                        used.add((xr, yr))
                        self._emit(f"  [{placed}] {figure_name} -> ({xr},{yr}) ✓ (tentativa {attempt+2})")
                        success = True
                        break
                    used.add((xr, yr))
                if not success:
                    self._emit(f"  {figure_name}: sem posicao valida apos varias tentativas.")

            elif http_status in (401,):
                self._emit(f"  Sessao expirada (HTTP {http_status}). Renovando token...")
                self._api.refresh_token()
                http2, _ = self._api.post(PLACE_PATH, {"figureId": figure_id, "x": x, "y": y})
                if 200 <= http2 < 300:
                    placed += 1
                    used.add((x, y))
                    self._emit(f"  [{placed}] {figure_name} -> ({x},{y}) ✓ (apos renovar token)")
                else:
                    self._emit(f"  Falha apos renovar token (HTTP {http2}). Abortando.")
                    break

            else:
                msg = str(resp) if resp else ""
                self._emit(f"  {figure_name}: HTTP {http_status} {msg[:100]}")

        return placed

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _sleep(self, seconds: float) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline and self._running and not self._stop_event.is_set():
            time.sleep(0.3)

    def _emit(self, msg: str) -> None:
        logger.info(msg)
        try: self.on_status(msg)
        except Exception: pass
