"""
debug_figures.py — Mostra o state de TODAS as figuras durante uma rodada ativa

Como usar:
  1. Abra o bot normalmente (Chrome logado)
  2. Durante uma rodada ativa (antes de colocar qualquer figura)
  3. python debug_figures.py
"""
import asyncio, json
from playwright.async_api import async_playwright

CDP_PORT = 9222
BASE = "https://nmt.gg"

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

JS_FETCH = """
async ([url, token]) => {
    const r = await fetch(url, {
        credentials: "include",
        headers: { "Accept": "application/json", "Authorization": "Bearer " + token }
    });
    return { status: r.status, body: await r.text() };
}
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

        token = await page.evaluate(JS_GET_TOKEN)
        print(f"Token: {'OK' if token else 'NAO ENCONTRADO'}\n")

        # Busca todas as figuras
        result = await page.evaluate(JS_FETCH, [BASE + "/api/figures?skip=0&take=100", token])
        data = json.loads(result['body'])
        items = data.get('items', [])

        print(f"Total de figuras no inventario: {len(items)}\n")
        print(f"{'Nome':<20} {'State':<15} {'Power':>6} {'MaxPower':>9} {'Level':>6} {'Kind':<10}")
        print("-" * 75)
        for f in items:
            name  = f.get('name', '?')[:19]
            state = f.get('state', '?')
            power = f.get('power', 0)
            maxp  = f.get('maxPower', 0)
            level = f.get('level', '?')
            kind  = f.get('kind', '?')
            marker = " <-- NAO IDLE" if state != "IDLE" else ""
            print(f"{name:<20} {state:<15} {power:>6} {maxp:>9} {level:>6} {kind:<10}{marker}")

        print(f"\nFiguras IDLE com power > 0: {len([f for f in items if f.get('state') == 'IDLE' and (f.get('power') or 0) > 0])}")
        print(f"Figuras com outro state: {[f.get('name') + '=' + f.get('state','?') for f in items if f.get('state') != 'IDLE']}")

        await browser.close()

asyncio.run(main())
