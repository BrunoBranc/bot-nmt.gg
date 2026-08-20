"""
test_socketio.py — Conecta ao socket.io do nmt.gg via Python e captura o live:ticket

Como usar:
  1. Abra o bot normalmente (Chrome logado)
  2. python test_socketio.py
  3. Me manda o output
"""
import asyncio, sys
from playwright.async_api import async_playwright

CDP_PORT = 9222

JS_GET_TOKEN = r"""
() => {
    for (const source of ["localStorage", "sessionStorage"]) {
        try {
            const s = window[source];
            for (let i = 0; i < s.length; i++) {
                const key = s.key(i);
                if (!(key.toLowerCase().includes("auth") || key.toLowerCase().includes("supabase") || key.startsWith("sb-"))) continue;
                try {
                    const p = JSON.parse(s.getItem(key));
                    if (p && p.access_token) return p.access_token;
                } catch(e) {}
            }
        } catch(e) {}
    }
    return null;
}
"""

async def get_token():
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
        token = await page.evaluate(JS_GET_TOKEN)
        await browser.close()
        return token

async def main():
    # 1. Pega o token JWT do Chrome
    print("Extraindo token JWT do Chrome...")
    token = await get_token()
    if not token:
        print("ERRO: Token nao encontrado.")
        return
    print(f"Token: {token[:30]}...\n")

    # 2. Conecta ao socket.io via python-socketio
    try:
        import socketio
    except ImportError:
        print("Instalando python-socketio e websocket-client...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install",
                       "python-socketio[client]", "websocket-client", "--break-system-packages", "-q"])
        import socketio

    sio = socketio.Client(logger=False, engineio_logger=False)
    ticket_received = asyncio.Event()
    ticket_value = [None]

    @sio.event
    def connect():
        print("Conectado ao socket.io!")

    @sio.event
    def disconnect():
        print("Desconectado do socket.io.")

    @sio.on("live:ticket")
    def on_ticket(data):
        print(f"\nlive:ticket recebido: {data}")
        ticket_value[0] = data
        ticket_received.set()

    @sio.on("*")
    def catch_all(event, data):
        print(f"Evento: {event} -> {str(data)[:100]}")

    print("Conectando ao socket.io de nmt.gg...")
    try:
        sio.connect(
            "https://nmt.gg",
            socketio_path="/socket.io",
            transports=["websocket", "polling"],
            auth={"token": token},
            wait_timeout=15
        )
    except Exception as e:
        print(f"ERRO ao conectar: {e}")
        return

    print("Aguardando evento live:ticket (30s)...")
    try:
        await asyncio.wait_for(ticket_received.wait(), timeout=30)
        print(f"\nSucesso! Ticket: {ticket_value[0]}")
    except asyncio.TimeoutError:
        print("\nTimeout — nenhum ticket recebido em 30s.")

    sio.disconnect()

asyncio.run(main())
