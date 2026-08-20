"""
debug_ticket.py — Descobre como o X-NMT-Live-Ticket e gerado

Como usar:
  1. Chrome aberto e logado no nmt.gg
  2. python debug_ticket.py
  3. Me manda o output
"""
import asyncio, json, re
from playwright.async_api import async_playwright

CDP_PORT = 9222
BASE = "https://nmt.gg"

# Intercepta multiplos places para ver se o ticket muda
JS_INTERCEPT_MULTI = """
() => {
    return new Promise((resolve) => {
        const results = [];
        const origFetch = window.fetch;
        window.fetch = async function(...args) {
            const [url, opts] = args;
            if (typeof url === 'string' && url.includes('power-blocks/place')) {
                const headers = {};
                if (opts && opts.headers) {
                    Object.assign(headers, opts.headers);
                }
                results.push({
                    headers,
                    body: opts && opts.body,
                    time: Date.now()
                });
                if (results.length >= 2) {
                    window.fetch = origFetch;
                    resolve(results);
                }
            }
            return origFetch(...args);
        };
        setTimeout(() => { window.fetch = origFetch; resolve(results); }, 60000);
    });
}
"""

# Procura a funcao que gera o ticket no escopo global
JS_FIND_TICKET_SOURCE = """
() => {
    const results = {};

    // Procura em window por funcoes relacionadas a ticket/live/nmt
    for (const key of Object.keys(window)) {
        const lower = key.toLowerCase();
        if (lower.includes('ticket') || lower.includes('live') || lower.includes('nmt') || lower.includes('hash')) {
            try {
                const val = window[key];
                results[key] = typeof val === 'function' ? 'function' : JSON.stringify(val)?.slice(0, 100);
            } catch(e) {}
        }
    }

    // Procura no __NEXT_DATA__ por qualquer referencia a ticket
    try {
        const nd = window.__NEXT_DATA__;
        if (nd) results['__NEXT_DATA__keys'] = Object.keys(nd);
    } catch(e) {}

    return results;
}
"""

# Tenta gerar o ticket com as mesmas entradas
JS_TRY_GENERATE = """
async ([figureId, x, y, roundId]) => {
    // Tenta usar a API de crypto do browser para gerar o hash
    // O ticket parece ser um SHA256 de alguma combinacao de dados
    const encoder = new TextEncoder();

    const candidates = [
        `${figureId}:${x}:${y}`,
        `${figureId}${x}${y}`,
        `${roundId}:${figureId}:${x}:${y}`,
        figureId,
        `place:${figureId}:${x}:${y}`,
    ];

    const results = {};
    for (const candidate of candidates) {
        const data = encoder.encode(candidate);
        const hashBuffer = await crypto.subtle.digest('SHA-256', data);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        results[candidate] = hashHex;
    }
    return results;
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

        # 1. Procura referencias a ticket no escopo global
        print("=== Variaveis globais relacionadas a ticket/live/nmt ===")
        ticket_vars = await page.evaluate(JS_FIND_TICKET_SOURCE)
        if ticket_vars:
            print(json.dumps(ticket_vars, indent=2))
        else:
            print("  Nenhuma encontrada.")

        # 2. Intercepta 2 places para ver se o ticket muda entre requests
        print("\n=== Interceptando 2 places manuais ===")
        print("Coloque DUAS figuras no tabuleiro manualmente (uma apos a outra)...")

        results = await page.evaluate(JS_INTERCEPT_MULTI)

        for i, r in enumerate(results):
            print(f"\n--- Place {i+1} ---")
            print(f"  Headers: {json.dumps(r['headers'], indent=4)}")
            print(f"  Body: {r['body']}")

        if len(results) >= 2:
            t1 = results[0]['headers'].get('X-NMT-Live-Ticket', '')
            t2 = results[1]['headers'].get('X-NMT-Live-Ticket', '')
            print(f"\n=== Comparacao dos tickets ===")
            print(f"  Ticket 1: {t1}")
            print(f"  Ticket 2: {t2}")
            print(f"  Sao iguais: {t1 == t2}")
            print(f"  Tamanho: {len(t1)} caracteres")

        await browser.close()

asyncio.run(main())
