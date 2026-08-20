"""
debug_round_events.py — Monitora eventos de fim de rodada via socket.io
para descobrir como o servidor notifica vencedores.

Deixa rodando ate uma rodada terminar.
"""
import asyncio, json, sys
from playwright.async_api import async_playwright
import socketio

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

JS_GET_USER_ID = """
async (token) => {
    const r = await fetch("https://nmt.gg/api/users/me", {
        credentials: "include",
        headers: { "Authorization": "Bearer " + token }
    });
    const d = await r.json();
    return d.id;
}
"""

async def get_token_and_user():
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
        user_id = await page.evaluate(JS_GET_USER_ID, token)
        await browser.close()
        return token, user_id

async def main():
    print("Extraindo token e user_id...")
    token, user_id = await get_token_and_user()
    print(f"Token: OK | User ID: {user_id}\n")
    print("Conectando ao socket.io e monitorando eventos de rodada...")
    print("Deixa rodar ate a rodada atual terminar.\n")

    sio = socketio.Client(logger=False, engineio_logger=False)

    @sio.event
    def connect():
        print("Conectado!\n")

    @sio.on("live:ticket")
    def on_ticket(data):
        pass  # ignora

    # Captura TODOS os eventos menos os muito frequentes
    IGNORE = {"explorer-activity", "pool-tick", "online-count", "price-tick"}

    @sio.on("*")
    def catch_all(event, data):
        if event in IGNORE:
            return
        print(f"\n[{event}]")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:600])

        # Verifica se o user_id aparece nos dados (vitoria!)
        data_str = json.dumps(data)
        if user_id and user_id in data_str:
            print(f"\n  *** SEU USER_ID APARECE NESTE EVENTO! ***")

    sio.connect(
        "https://nmt.gg",
        socketio_path="/socket.io",
        transports=["websocket", "polling"],
        auth={"token": token},
        wait_timeout=15,
    )

    print("Aguardando eventos (Ctrl+C para parar)...\n")
    try:
        await asyncio.sleep(700)  # aguarda ate ~1 rodada completa
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass

    sio.disconnect()

asyncio.run(main())
