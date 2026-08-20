"""
debug_place.py — Testa o POST /api/power-blocks/place diretamente
e inspeciona headers necessarios.

Como usar:
  1. Chrome aberto e logado no nmt.gg
  2. Entre em uma rodada ativa
  3. python debug_place.py
  4. Me manda o output
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
                const lower = key.toLowerCase();
                if (!(lower.includes("auth") || lower.includes("supabase") || lower.startsWith("sb-"))) continue;
                try {
                    const parsed = JSON.parse(s.getItem(key));
                    if (parsed && parsed.access_token) return parsed.access_token;
                    if (parsed && parsed.session && parsed.session.access_token) return parsed.session.access_token;
                } catch(e) {}
            }
        } catch(e) {}
    }
    return null;
}
"""

# Intercepta o proximo POST de place para capturar headers reais
JS_INTERCEPT = """
() => {
    return new Promise((resolve) => {
        const origFetch = window.fetch;
        window.fetch = async function(...args) {
            const [url, opts] = args;
            if (typeof url === 'string' && url.includes('power-blocks/place')) {
                const headers = {};
                if (opts && opts.headers) {
                    const h = opts.headers;
                    if (h instanceof Headers) {
                        h.forEach((v, k) => headers[k] = v);
                    } else {
                        Object.assign(headers, h);
                    }
                }
                window.fetch = origFetch;
                resolve({ url, headers, body: opts && opts.body });
                return origFetch(...args);
            }
            return origFetch(...args);
        };
        setTimeout(() => resolve(null), 30000);
    });
}
"""

JS_GET = """
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

        print(f"Aba: {page.url}\n")

        # 1. Pega token
        token = await page.evaluate(JS_GET_TOKEN)
        print(f"Token: {'SIM (' + token[:25] + '...)' if token else 'NAO'}\n")

        # 2. Pega uma figura IDLE para testar
        result = await page.evaluate(JS_GET, [BASE + "/api/figures?skip=0&take=5", token])
        figures_data = json.loads(result['body'])
        idle = [f for f in figures_data.get('items', []) if f.get('state') == 'IDLE']
        print(f"Figuras IDLE disponiveis: {len(idle)}")
        for f in idle:
            print(f"  - {f['name']} (id={f['id']}, state={f.get('state')})")

        if not idle:
            print("\nNenhuma figura IDLE. Rode durante uma rodada ativa.")
            await browser.close()
            return

        # 3. Instala interceptor para capturar headers do proximo place manual
        print("\n" + "="*60)
        print("PASSO: Coloque UMA figura NO TABULEIRO MANUALMENTE agora.")
        print("O script vai capturar os headers exatos do request.")
        print("="*60)

        intercept_task = asyncio.create_task(page.evaluate(JS_INTERCEPT))

        captured = await intercept_task
        print(f"\nRequest interceptado:")
        if captured:
            print(f"  URL: {captured.get('url')}")
            print(f"  Headers: {json.dumps(captured.get('headers', {}), indent=4)}")
            print(f"  Body: {captured.get('body')}")
        else:
            print("  Timeout - nenhum place detectado em 30s.")

        await browser.close()

asyncio.run(main())
