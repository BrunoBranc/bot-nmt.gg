"""
debug_read_ticket.py — Le o ticket diretamente do modulo webpack 3442

Como usar:
  1. Abra o bot, inicie normalmente
  2. python debug_read_ticket.py
  3. Me manda o output
"""
import asyncio, json
from playwright.async_api import async_playwright

CDP_PORT = 9222

# Le o ticket diretamente da variavel 'o' do modulo 3442
# e tambem expoe a funcao x_() para chamadas futuras
JS_READ_AND_EXPOSE = """
() => {
    try {
        // Acessa o cache de modulos do webpack
        const cache = window.__webpack_require__?.c || {};

        // Procura o modulo 3442 no cache
        const mod = cache['3442'];
        if (!mod) return { error: 'modulo 3442 nao encontrado no cache' };

        const exports = mod.exports;
        if (!exports) return { error: 'exports vazio' };

        // Lista o que o modulo exporta
        const keys = Object.keys(exports);

        // Chama x_() que e a funcao que retorna o ticket
        let ticket = null;
        if (typeof exports.x_ === 'function') {
            // x_() e async - retorna Promise
            // Mas internamente so retorna 'o' que ja esta carregado
            // Vamos chamar de forma sincrona via hack
            ticket = 'x_ found - needs async call';
        }

        // Tenta ler 'o' direto inspecionando o closure da funcao
        // A funcao hb() conecta o socket - tenta chamar para forcar conexao
        let socketState = 'unknown';
        if (typeof exports.hb === 'function') {
            socketState = 'hb() found';
        }

        return {
            moduleFound: true,
            exportKeys: keys,
            hasX_: typeof exports.x_ === 'function',
            hasHb: typeof exports.hb === 'function',
            hasTb: typeof exports.Tb === 'function',
            hasMb: typeof exports.mB !== 'undefined',
            ticket,
            socketState
        };
    } catch(e) {
        return { error: String(e) };
    }
}
"""

# Chama x_() de forma async e retorna o ticket
JS_CALL_X_ = """
async () => {
    try {
        const cache = window.__webpack_require__?.c || {};
        const mod = cache['3442'];
        if (!mod) return { error: 'modulo 3442 nao no cache' };
        const x_ = mod.exports?.x_;
        if (!x_) return { error: 'x_ nao encontrado' };
        const ticket = await x_();
        return { ticket };
    } catch(e) {
        return { error: String(e) };
    }
}
"""

# Forca a conexao do socket chamando hb() e aguarda o ticket chegar
JS_CONNECT_SOCKET_AND_WAIT = """
async () => {
    try {
        const cache = window.__webpack_require__?.c || {};
        const mod = cache['3442'];
        if (!mod) return { error: 'modulo 3442 nao no cache' };

        const { hb, x_ } = mod.exports || {};

        // Conecta o socket (hb = funcao que cria/conecta o socket)
        if (hb) hb();

        // Aguarda ate 10s pelo ticket
        for (let i = 0; i < 20; i++) {
            await new Promise(r => setTimeout(r, 500));
            try {
                const ticket = await x_();
                if (ticket) return { ticket, attempts: i+1 };
            } catch(e) {}
        }
        return { error: 'timeout aguardando ticket do socket' };
    } catch(e) {
        return { error: String(e) };
    }
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

        # 1. Inspeciona o modulo
        print("=== Modulo 3442 ===")
        info = await page.evaluate(JS_READ_AND_EXPOSE)
        print(json.dumps(info, indent=2))

        # 2. Chama x_() diretamente
        print("\n=== Chamando x_() diretamente ===")
        result = await page.evaluate(JS_CALL_X_)
        print(json.dumps(result, indent=2))

        # 3. Se falhou, tenta conectar socket e aguardar
        if result.get('error'):
            print("\n=== Conectando socket e aguardando ticket ===")
            result2 = await page.evaluate(JS_CONNECT_SOCKET_AND_WAIT)
            print(json.dumps(result2, indent=2))

        await browser.close()

asyncio.run(main())
