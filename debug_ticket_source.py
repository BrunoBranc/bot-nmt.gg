"""
debug_ticket_source.py — Encontra a funcao que gera o ticket no JS do Next.js

Como usar:
  1. Abra o bot normalmente
  2. python debug_ticket_source.py
"""
import asyncio, json, re
from playwright.async_api import async_playwright

CDP_PORT = 9222
BASE = "https://nmt.gg"

# Busca nos chunks do Next.js por codigo relacionado ao ticket
JS_SEARCH_CHUNKS = """
async () => {
    const scripts = Array.from(document.querySelectorAll('script[src]'))
        .map(s => s.src)
        .filter(s => s.includes('_next/static'));

    const hits = [];
    for (const src of scripts) {
        try {
            const r = await fetch(src);
            const text = await r.text();
            const lower = text.toLowerCase();

            // Procura por "live" perto de "ticket" ou "x-nmt"
            const patterns = ['x-nmt', 'liveticket', 'live-ticket', 'live_ticket', 'livetoken',
                              'pfversion', 'pf_version', 'pfv', 'provably'];
            for (const pat of patterns) {
                let idx = lower.indexOf(pat);
                while (idx !== -1) {
                    const snippet = text.slice(Math.max(0, idx-120), idx+200);
                    hits.push({ file: src.split('/').pop(), pat, snippet });
                    idx = lower.indexOf(pat, idx + 1);
                    if (hits.length > 30) return hits;
                }
            }
        } catch(e) {}
    }
    return hits;
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
        print("Procurando ticket nos chunks JS do Next.js...\n")

        hits = await page.evaluate(JS_SEARCH_CHUNKS)
        if not hits:
            print("Nenhum resultado encontrado.")
        for h in hits:
            print(f"[{h['file']}] pattern={h['pat']}")
            print(f"  {h['snippet']}\n")

        await browser.close()

asyncio.run(main())
