"""
debug_find_module.py v2 — Acessa o modulo via webpackChunk_N_E
"""
import asyncio, json
from playwright.async_api import async_playwright

CDP_PORT = 9222

JS_FIND_VIA_CHUNK = """
async () => {
    const results = {};

    // webpackChunk_N_E e o array global de chunks do Next.js
    const chunks = window.webpackChunk_N_E;
    if (!chunks) return { error: 'webpackChunk_N_E nao encontrado' };
    results.chunks = chunks.length;

    // O webpack expoe __webpack_require__ dentro do chunk push
    // Vamos interceptar o push para capturar o require interno
    let capturedRequire = null;
    const origPush = chunks.push.bind(chunks);
    chunks.push = function(chunk) {
        // chunk = [chunkIds, moreModules, runtime]
        const runtime = chunk[2];
        if (typeof runtime === 'function') {
            const fake = {
                e: () => Promise.resolve(),
                d: (obj, defs) => { Object.assign(obj, defs); },
                r: () => {},
                o: (obj, key) => Object.prototype.hasOwnProperty.call(obj, key),
                n: (m) => m.__esModule ? () => m.default : () => m,
            };
            try {
                runtime(fake);
                if (!capturedRequire) capturedRequire = fake;
            } catch(e) {}
        }
        return origPush(chunk);
    };

    // Tenta outra abordagem: procura nos modulos ja instalados via chunk
    // O Next.js guarda modulos em chunks[i][1]
    for (const chunk of chunks) {
        if (!Array.isArray(chunk) || chunk.length < 2) continue;
        const modules = chunk[1];
        if (!modules || typeof modules !== 'object') continue;

        for (const [id, fn] of Object.entries(modules)) {
            if (typeof fn !== 'function') continue;
            const src = fn.toString();
            if (!src.includes('live:ticket') && !src.includes('x_')) continue;

            results.candidateModule = id;
            results.src = src.slice(0, 800);

            // Tenta executar o modulo para obter seus exports
            try {
                const fakeModule = { exports: {} };
                const fakeRequire = (id) => {
                    // Retorna um socket.io fake para evitar conexao real
                    if (String(id).includes('17425') || String(id).includes('socket')) {
                        return {
                            io: (path, opts) => ({
                                on: () => {},
                                connect: () => {},
                                disconnect: () => {},
                                connected: false
                            })
                        };
                    }
                    return {};
                };
                fakeRequire.d = (obj, defs) => {
                    for (const [key, getter] of Object.entries(defs)) {
                        Object.defineProperty(obj, key, { get: getter, enumerable: true });
                    }
                };
                fakeRequire.o = () => false;
                fakeRequire.r = () => {};
                fakeRequire.n = (m) => () => m;
                fakeRequire.e = () => Promise.resolve();

                fn(fakeModule, fakeModule.exports, fakeRequire);
                const exp = fakeModule.exports;
                results.exportKeys = Object.keys(exp);

                if (typeof exp.x_ === 'function') {
                    results.hasX_ = true;
                    // Tenta chamar x_()
                    try {
                        const ticket = await exp.x_();
                        results.ticket = ticket;
                    } catch(e) {
                        results.x_error = String(e);
                    }
                }
            } catch(e) {
                results.execError = String(e);
            }
            break;
        }
        if (results.candidateModule) break;
    }

    chunks.push = origPush;
    return results;
}
"""

# Alternativa: intercepta o fetch que o SITE faz e copia os headers
JS_PATCH_FETCH_PERMANENT = """
() => {
    // Instala um patch que salva o ticket de QUALQUER fetch com X-NMT-Live-Ticket
    // incluindo os feitos pelo codigo interno do Next.js
    if (window.__nmtPatchInstalled) return 'already installed';

    const orig = window.fetch;
    window.__nmtLiveTicket = null;
    window.__nmtPatchInstalled = true;

    window.fetch = function(...args) {
        const [url, opts] = args;
        if (opts?.headers) {
            const ticket = opts.headers['X-NMT-Live-Ticket'] ||
                          (opts.headers instanceof Headers
                            ? opts.headers.get('X-NMT-Live-Ticket')
                            : null);
            if (ticket) {
                window.__nmtLiveTicket = ticket;
                console.log('[NMT Bot] Ticket capturado:', ticket.slice(0,16));
            }
        }
        return orig.apply(this, args);
    };
    return 'installed';
}
"""

JS_READ_TICKET = "() => window.__nmtLiveTicket"

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

        # 1. Tenta via chunk
        print("=== Tentando via webpackChunk_N_E ===")
        r = await page.evaluate(JS_FIND_VIA_CHUNK)
        print(json.dumps(r, indent=2))

        # 2. Instala patch permanente no fetch
        print("\n=== Instalando patch permanente no fetch ===")
        r2 = await page.evaluate(JS_PATCH_FETCH_PERMANENT)
        print(f"Resultado: {r2}")

        # 3. Le ticket atual (se houver)
        ticket = await page.evaluate(JS_READ_TICKET)
        print(f"Ticket atual: {ticket}")

        if not ticket:
            print("\nAguardando 30s por um place do site (manual ou automatico)...")
            import time
            for i in range(30):
                await asyncio.sleep(1)
                ticket = await page.evaluate(JS_READ_TICKET)
                if ticket:
                    print(f"Ticket capturado apos {i+1}s: {ticket}")
                    break
            if not ticket:
                print("Nenhum ticket capturado em 30s.")

        await browser.close()

asyncio.run(main())
