"""
debug_ticket_storage.py — Descobre onde o X-NMT-Live-Ticket fica armazenado
na memoria do site (variavel global, React state, window object, etc.)

Como usar:
  1. Abra o bot normalmente e selecione a aba
  2. python debug_ticket_storage.py
"""
import asyncio, json
from playwright.async_api import async_playwright

CDP_PORT = 9222

# Procura o ticket em todas as variaveis acessiveis do window
JS_FIND_TICKET = """
async (knownTicket) => {
    const results = {};

    // 1. Procura direto no window por qualquer valor igual ao ticket
    for (const key of Object.keys(window)) {
        try {
            const val = window[key];
            if (typeof val === 'string' && val === knownTicket) {
                results['window.' + key] = val;
            }
            if (typeof val === 'object' && val !== null) {
                const str = JSON.stringify(val);
                if (str && str.includes(knownTicket)) {
                    results['window.' + key + ' (object)'] = 'CONTAINS TICKET';
                }
            }
        } catch(e) {}
    }

    // 2. Procura em __NEXT_DATA__ (Next.js state)
    try {
        const nd = JSON.stringify(window.__NEXT_DATA__);
        if (nd && nd.includes(knownTicket)) results['__NEXT_DATA__'] = 'CONTAINS TICKET';
    } catch(e) {}

    // 3. Procura em React fiber (componentes montados)
    try {
        const root = document.getElementById('__next') || document.querySelector('[data-reactroot]');
        if (root) {
            const fiberKey = Object.keys(root).find(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance'));
            if (fiberKey) {
                // Navega pelo fiber tree procurando o ticket
                const searchFiber = (fiber, depth = 0) => {
                    if (depth > 20 || !fiber) return false;
                    try {
                        const str = JSON.stringify(fiber.memoizedState || {});
                        if (str && str.includes(knownTicket)) {
                            results['React fiber (depth ' + depth + ')'] = 'CONTAINS TICKET';
                            return true;
                        }
                    } catch(e) {}
                    return searchFiber(fiber.child, depth + 1) || searchFiber(fiber.sibling, depth + 1);
                };
                searchFiber(root[fiberKey]);
            }
        }
    } catch(e) { results['react_error'] = String(e); }

    // 4. Procura em cookies
    try {
        if (document.cookie.includes(knownTicket)) results['cookie'] = 'CONTAINS TICKET';
    } catch(e) {}

    // 5. Procura em sessionStorage e localStorage
    for (const storage of ['localStorage', 'sessionStorage']) {
        try {
            const s = window[storage];
            for (let i = 0; i < s.length; i++) {
                const key = s.key(i);
                const val = s.getItem(key);
                if (val && val.includes(knownTicket)) {
                    results[storage + '.' + key] = 'CONTAINS TICKET';
                }
            }
        } catch(e) {}
    }

    return results;
}
"""

# Intercepta o proximo place para pegar o ticket atual
JS_GET_TICKET = """
() => new Promise((resolve) => {
    const orig = window.fetch;
    window.fetch = async function(...args) {
        const [url, opts] = args;
        if (typeof url === 'string' && url.includes('power-blocks/place')) {
            window.fetch = orig;
            resolve((opts?.headers || {})['X-NMT-Live-Ticket'] || null);
            return orig(...args);
        }
        return orig(...args);
    };
    setTimeout(() => { window.fetch = orig; resolve(null); }, 30000);
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

        # Pega o ticket via intercept (coloque uma figura manualmente)
        print("Coloque UMA figura manualmente para capturar o ticket atual...")
        ticket = await page.evaluate(JS_GET_TICKET)
        if not ticket:
            print("Timeout. Nenhuma figura colocada.")
            await browser.close()
            return

        print(f"Ticket capturado: {ticket}\n")
        print("Procurando onde o ticket fica armazenado...\n")

        results = await page.evaluate(JS_FIND_TICKET, ticket)
        if results:
            print("ENCONTRADO em:")
            for k, v in results.items():
                print(f"  {k}: {v}")
        else:
            print("Ticket NAO encontrado em nenhuma variavel acessivel do window.")
            print("Provavelmente gerado dinamicamente a cada request pelo codigo compilado do Next.js.")

        await browser.close()

asyncio.run(main())
