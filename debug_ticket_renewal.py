"""
debug_ticket_renewal.py v3 — Monitora requests relevantes e mostra bodies.
Ignora /api/power-blocks/current para nao poluir o log.

Deixa rodando ate o ticket expirar e bugarem as figuras.
"""
import asyncio
from playwright.async_api import async_playwright

CDP_PORT = 9222

JS_MONITOR = """
() => new Promise((resolve) => {
    const log = [];
    const IGNORE = ['/api/power-blocks/current', '/uploads/', '.webp', '.png', '.svg'];
    const orig = window.fetch;

    window.fetch = async function(...args) {
        const [url, opts] = args;
        const urlStr = typeof url === 'string' ? url : String(url);
        const skip = IGNORE.some(p => urlStr.includes(p));

        let resBody = null, status = null;
        try {
            const response = await orig.apply(this, args);
            status = response.status;
            if (!skip) {
                try { resBody = await response.clone().text(); } catch(e) {}
                if (resBody && resBody.length > 600) resBody = resBody.slice(0, 600) + '...';
            }
            if (!skip && log.length < 200) {
                log.push({
                    time: new Date().toISOString().slice(11,19),
                    method: (opts?.method || 'GET').toUpperCase(),
                    url: urlStr.replace('https://nmt.gg', ''),
                    reqHeaders: opts?.headers ? {...opts.headers} : {},
                    status,
                    body: resBody
                });
            }
            return response;
        } catch(e) {
            if (!skip) log.push({ time: new Date().toISOString().slice(11,19), url: urlStr, error: String(e) });
            throw e;
        }
    };

    setTimeout(() => { window.fetch = orig; resolve(log); }, 300000); // 5 min
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
        print(f"Aba: {page.url}")
        print("Monitorando (sem /current). Deixa rodar ate o ticket bugs. Ctrl+C para parar.\n")

        try:
            log = await page.evaluate(JS_MONITOR)
        except (KeyboardInterrupt, Exception):
            log = []

        print(f"\n{'='*60}")
        print(f"Total de requests relevantes: {len(log)}\n")
        for e in log:
            ticket = e.get('reqHeaders', {}).get('X-NMT-Live-Ticket', '')
            auth = 'yes' if e.get('reqHeaders', {}).get('Authorization') else 'no'
            print(f"[{e.get('time','')}] {e.get('method','?')} {e.get('url','')} -> {e.get('status','?')} (auth={auth})")
            if ticket: print(f"  Ticket: {ticket}")
            if e.get('body'): print(f"  Body:   {e['body'][:400]}")
            if e.get('error'): print(f"  ERROR:  {e['error']}")

        await browser.close()

asyncio.run(main())
