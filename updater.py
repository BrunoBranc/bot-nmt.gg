"""
updater.py — Verifica se ha atualizacao disponivel no GitHub Releases.

Coloque na raiz do projeto (mesma pasta do main.py).
"""
from __future__ import annotations

import json
import threading
import urllib.request
from typing import Callable, Optional

from version import __version__, GITHUB_REPO


def _parse_version(v: str) -> tuple[int, ...]:
    """Converte '1.2.3' em (1, 2, 3) para comparacao."""
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0,)


def check_for_update(
    on_update_available: Callable[[str, str], None],
    on_error: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Verifica em background se ha nova versao no GitHub Releases.
    Chama on_update_available(versao_nova, url_download) se houver.
    Chama on_error(mensagem) em caso de falha (opcional).
    """
    def _check():
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "NMTBot"},
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())

            latest_tag  = data.get("tag_name", "").lstrip("v")
            release_url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")

            # Procura o .exe nos assets
            for asset in data.get("assets", []):
                if asset.get("name", "").endswith(".exe"):
                    release_url = asset.get("browser_download_url", release_url)
                    break

            if not latest_tag:
                return

            if _parse_version(latest_tag) > _parse_version(__version__):
                on_update_available(latest_tag, release_url)

        except Exception as e:
            if on_error:
                on_error(str(e))

    threading.Thread(target=_check, daemon=True).start()
