r"""Camada de configurações persistida (JSON) para a GUI."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Settings:
    """Gerencia configurações persistidas em JSON."""

    _DEFAULTS: dict[str, Any] = {
        # Navegador
        "headless": False,
        # Engine
        "loop_interval": 5.0,
        "poll_interval": 3.0,
        "max_figures_per_round": 5,
        # Humanizer
        "humanize_base_delay_min": 150,
        "humanize_base_delay_max": 450,
        "humanize_click_delay_min": 80,
        "humanize_click_delay_max": 220,
        "humanize_round_delay_min": 800,
        "humanize_round_delay_max": 2200,
        # UI
        "window_geometry": "820x560",
        # Cloudflare
        "cloudflare_auto_timeout": 45.0,
        "cloudflare_manual_timeout": 180.0,
    }

    def __init__(self, path: Path | None = None):
        self._path = path or (Path(__file__).resolve().parents[2] / "data" / "settings.json")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        try:
            if self._path.exists():
                with self._path.open("r", encoding="utf-8") as f:
                    self._data = json.load(f)
        except Exception:
            self._data = {}
        # Merge com defaults
        for k, v in self._DEFAULTS.items():
            self._data.setdefault(k, v)

    def save(self) -> None:
        try:
            with self._path.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            # silencioso — não derruba a app por erro de config
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, self._DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def update(self, mapping: dict[str, Any]) -> None:
        self._data.update(mapping)

    def get_all(self) -> dict[str, Any]:
        return dict(self._data)

    # Convenience typed getters
    def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(key, default))
        except Exception:
            return float(self._DEFAULTS.get(key, default))

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get(key, default))
        except Exception:
            return int(self._DEFAULTS.get(key, default))

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.get(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes", "on")
        return bool(val)

    def get_str(self, key: str, default: str = "") -> str:
        return str(self.get(key, default))


# Instância global
_settings = None

def get_settings(path: Path | None = None) -> "Settings":
    global _settings
    if _settings is None:
        _settings = Settings(path)
    return _settings