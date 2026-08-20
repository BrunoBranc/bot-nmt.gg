"""
debug_api.py v2 — Descobre token e testa endpoints com autenticacao correta
"""
import asyncio, json
from playwright.async_api import async_playwright

CDP_PORT = 9222
BASE = "https://nmt.gg"

# Extrai o token JWT do localStorage (mesmo metodo do TokenExtractor)
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

JS_FETCH_AUTH = """
async ([url, token]) => {
    const headers = { "Accept": "application/json" };
    if (token) headers["Authorization"] = "Bearer " + token;
    const r = await fetch(url, { credentials: "include", headers });
    return { status: r.status, body: await r.text() };
}
"""

async def fetch_auth(page, path, token=None):
    result = await page.evaluate(JS_FETCH_AUTH, [BASE + path, token])
    status = result['status']
    print(f"\n{'='*60}")
    print(f"GET {path}  ->  HTTP {status}")
    try:
        data = json.loads(result['body'])
        print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
        return status, data
    except:
        print(result['body'][:300])
        return status, None

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

        # 1. Extrai token
        token = await page.evaluate(JS_GET_TOKEN)
        print(f"Token encontrado: {'SIM (' + token[:30] + '...)' if token else 'NAO'}")

        # 2. Testa /api/figures com Authorization header
        await fetch_auth(page, "/api/figures?skip=0&take=5", token)

        # 3. Testa /api/power-blocks/current com token (para comparar)
        await fetch_auth(page, "/api/power-blocks/current", token)

        # 4. Testa endpoint de figuras da rodada/dock
        for path in [
            "/api/power-blocks/my-placements",
            "/api/power-blocks/my-figures",
            "/api/figures/power-blocks",
            "/api/user/figures",
            "/api/inventory",
            "/api/figures?skip=0&take=5&available=true",
            "/api/figures?skip=0&take=5&type=power-blocks",
        ]:
            status, _ = await fetch_auth(page, path, token)

        await browser.close()

asyncio.run(main())
