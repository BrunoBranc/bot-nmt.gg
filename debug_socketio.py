"""
debug_socketio.py — Confirma que o ticket vem via Socket.IO e le o valor atual

Como usar:
  1. Abra o bot normalmente
  2. python debug_socketio.py
"""
import asyncio
from playwright.async_api import async_playwright

CDP_PORT = 9222

# Inspeciona o socket.io ativo na pagina e le o ticket
JS_READ_SOCKETIO_TICKET = """
() => {
    const results = {};

    // Procura a instancia do socket.io no escopo global
    // O site usa (0,r.io)("/", ...) - a instancia fica em algum closure
    // Mas o ticket em si fica em uma variavel que a funcao x_() acessa

    // Tenta achar via manager do socket.io
    try {
        if (window.io) results['window.io'] = 'found';
    } catch(e) {}

    // Procura em todas as keys do window por objetos com 'socket' ou 'emit'
    for (const key of Object.keys(window)) {
        try {
            const v = window[key];
            if (v && typeof v === 'object') {
                if (typeof v.emit === 'function' && typeof v.on === 'function') {
                    results['socket_candidate:' + key] = Object.keys(v).slice(0, 10).join(', ');
                }
            }
        } catch(e) {}
    }

    // O ticket provavelmente fica em um modulo webpack - tenta acessar via __webpack_require__
    try {
        const req = window.__webpack_require__ || window.webpackChunk_N_E;
        if (req) results['webpack'] = typeof req;
    } catch(e) {}

    // Tenta ler o ticket via React context / hooks armazenados em closures
    // Procura em event listeners registrados no document
    const listeners = window._nmtDebugListeners || [];
    results['listeners'] = listeners.length;

    return results;
}
"""

# Instala um listener no socket.io para capturar o ticket em tempo real
JS_INTERCEPT_SOCKET = """
() => new Promise((resolve) => {
    // Intercepta o EventSource / WebSocket para capturar o ticket
    const results = { websockets: [], tickets: [] };

    // Monkey-patch WebSocket para ver conexoes
    const OrigWS = window.WebSocket;
    const sockets = [];
    window.WebSocket = function(url, protocols) {
        const ws = new OrigWS(url, protocols);
        results.websockets.push(url);
        ws.addEventListener('message', (e) => {
            const data = String(e.data);
            if (data.includes('live:ticket') || data.includes('ticket')) {
                results.tickets.push({ url, data: data.slice(0, 300) });
            }
        });
        sockets.push(ws);
        return ws;
    };
    window.WebSocket.prototype = OrigWS.prototype;

    setTimeout(() => {
        window.WebSocket = OrigWS;
        resolve(results);
    }, 30000);
})
"""

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        page = None
        for ctx in browser.contexts:
            for p in ctx.pages:
                if "nmt.gg" in p.url:
                    page = p
                    break
        if not page:
            page = browser.contexts[0].pages[0]
        print(f"Aba: {page.url}\n")

        # 1. Inspeciona o que existe na pagina
        print("=== Inspecionando socket/ticket na pagina ===")
        info = await page.evaluate(JS_READ_SOCKETIO_TICKET)
        import json
        print(json.dumps(info, indent=2))

        # 2. Tenta ler o ticket expondo a funcao x_() do modulo webpack
        print("\n=== Tentando expor a funcao x_() que gera o ticket ===")
        JS_EXPOSE_TICKET_FN = """
        async () => {
            // O chunk 9997 exporta x_() - tenta acha-la via webpack modules
            try {
                // webpack chunk global
                const chunks = window.webpackChunk_N_E || [];
                for (const chunk of chunks) {
                    if (!Array.isArray(chunk) || chunk.length < 2) continue;
                    const modules = chunk[1];
                    for (const [id, fn] of Object.entries(modules || {})) {
                        try {
                            const src = fn.toString();
                            if (src.includes('live:ticket') || src.includes('X-NMT-Live-Ticket')) {
                                return { found: true, moduleId: id, src: src.slice(0, 500) };
                            }
                        } catch(e) {}
                    }
                }
            } catch(e) { return { error: String(e) }; }
            return { found: false };
        }
        """
        result = await page.evaluate(JS_EXPOSE_TICKET_FN)
        print(json.dumps(result, indent=2))

        # 3. Monitora WebSocket por 30s para ver o ticket chegar
        print("\n=== Monitorando WebSocket por 30s (aguarda ticket via socket.io) ===")
        ws_result = await page.evaluate(JS_INTERCEPT_SOCKET)
        print(f"WebSockets detectados: {ws_result.get('websockets', [])}")
        print(f"Mensagens com ticket: {ws_result.get('tickets', [])}")

        await browser.close()

asyncio.run(main())
