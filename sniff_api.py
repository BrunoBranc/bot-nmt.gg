"""
sniff_api.py — Descobridor de endpoints da API do nmt.gg

Como usar:
  1. Abra o Chrome normalmente pelo bot (clique em "Abrir Navegador")
  2. Faça login no nmt.gg e entre em uma partida
  3. Rode este script: python sniff_api.py
  4. Jogue UMA rodada manualmente (coloque uma figura no tabuleiro)
  5. Pressione Ctrl+C para parar
  6. Copie o output e me mande

O script vai imprimir todos os requests/responses da API do nmt.gg.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from playwright.async_api import async_playwright

CDP_PORT = 9222
TARGET_DOMAIN = "nmt.gg"


async def main():
    print(f"[sniff] Conectando ao Chrome na porta {CDP_PORT}...")
    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        except Exception as e:
            print(f"[ERRO] Nao foi possivel conectar ao Chrome: {e}")
            print("Certifique-se de que o Chrome esta aberto pelo bot (porta 9222).")
            sys.exit(1)

        # Pega a primeira aba com nmt.gg
        page = None
        for ctx in browser.contexts:
            for p in ctx.pages:
                if TARGET_DOMAIN in p.url:
                    page = p
                    break
            if page:
                break

        if not page:
            # Fallback: pega a primeira aba disponivel
            for ctx in browser.contexts:
                if ctx.pages:
                    page = ctx.pages[0]
                    break

        if not page:
            print("[ERRO] Nenhuma aba encontrada no Chrome.")
            sys.exit(1)

        print(f"[sniff] Monitorando aba: {page.url}")
        print("[sniff] Agora jogue UMA rodada manualmente. Pressione Ctrl+C para parar.\n")
        print("=" * 70)

        captured = []

        async def on_request(request):
            url = request.url
            if TARGET_DOMAIN not in url:
                return
            entry = {
                "time": time.strftime("%H:%M:%S"),
                "method": request.method,
                "url": url,
                "headers": dict(request.headers),
                "post_data": None,
            }
            try:
                pd = request.post_data
                if pd:
                    try:
                        entry["post_data"] = json.loads(pd)
                    except Exception:
                        entry["post_data"] = pd
            except Exception:
                pass
            captured.append(entry)

            print(f"\n>>> REQUEST [{entry['time']}]")
            print(f"    {entry['method']} {url}")
            if entry["post_data"]:
                print(f"    BODY: {json.dumps(entry['post_data'], indent=6, ensure_ascii=False)}")

        async def on_response(response):
            url = response.url
            if TARGET_DOMAIN not in url:
                return
            try:
                body = await response.json()
            except Exception:
                try:
                    body = await response.text()
                    if len(body) > 500:
                        body = body[:500] + "... [truncado]"
                except Exception:
                    body = "(sem body)"

            print(f"\n<<< RESPONSE [{response.status}] {url}")
            if isinstance(body, dict):
                print(f"    KEYS: {list(body.keys())}")
                print(f"    BODY: {json.dumps(body, indent=6, ensure_ascii=False)[:800]}")
            else:
                print(f"    BODY: {str(body)[:400]}")

        page.on("request", on_request)
        page.on("response", on_response)

        print("[sniff] Aguardando requisicoes... (Ctrl+C para parar)\n")
        try:
            await asyncio.sleep(300)  # 5 minutos de captura
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass

        print("\n" + "=" * 70)
        print(f"[sniff] Total de requisicoes capturadas: {len(captured)}")
        print("\n[sniff] Resumo de endpoints encontrados:")
        seen = set()
        for e in captured:
            key = f"{e['method']} {e['url'].split('?')[0]}"
            if key not in seen:
                seen.add(key)
                print(f"  {key}")

        await browser.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
