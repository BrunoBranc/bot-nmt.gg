r"""Utilitarios de humanizacao para anti-deteccao.

Fornece delays gaussianos, jitter, movimentos de mouse naturais e variacao
de timing para tornar o comportamento do bot menos previsivel.
"""
from __future__ import annotations

import math
import random
import time
from typing import Optional


class Humanizer:
    """Gerador de comportamentos humanizados para o bot."""

    # Parametros base (ajustaveis conforme necessidade)
    BASE_DELAY_MS: tuple[float, float] = (150, 450)      # delay base entre acoes (ms)
    CLICK_DELAY_MS: tuple[float, float] = (80, 220)      # delay entre cliques (ms)
    ROUND_DELAY_MS: tuple[float, float] = (800, 2200)    # delay entre rounds (ms)
    SAFETY_DELAY_MS: tuple[float, float] = (3000, 8000)  # delay de seguranca (ms)

    # Parametros de movimento do mouse
    MOUSE_SPEED_PX_MS: tuple[float, float] = (800, 2000)  # velocidade do mouse (px/s)
    OVERSHOOT_PROB: float = 0.15                          # probabilidade de overshoot
    OVERSHOOT_MAX_PX: int = 12                            # overshoot maximo (px)
    JITTER_PX: int = 3                                    # jitter final (px)

    # Parametros de variacao comportamental
    PAUSE_PROB: float = 0.08                              # probabilidade de pausa extra
    PAUSE_EXTRA_MS: tuple[float, float] = (500, 2000)     # pausa extra (ms)
    ERROR_RECOVERY_MS: tuple[float, float] = (1000, 3000) # recuperacao apos erro (ms)

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)

    # -----------------------
    # Delays base
    # -----------------------
    def base_delay(self) -> float:
        """Delay base entre acoes (segundos). Distribuicao log-normal suave."""
        lo, hi = self.BASE_DELAY_MS
        mean = (lo + hi) / 2000.0
        sigma = 0.25
        val = self._rng.lognormvariate(mean * 0.9, sigma)
        return max(lo / 1000.0, min(hi / 1000.0, val))

    def click_delay(self) -> float:
        """Delay entre cliques consecutivos (segundos)."""
        lo, hi = self.CLICK_DELAY_MS
        return self._rng.uniform(lo, hi) / 1000.0

    def round_delay(self) -> float:
        """Delay entre rounds (segundos)."""
        lo, hi = self.ROUND_DELAY_MS
        return self._rng.uniform(lo, hi) / 1000.0

    def safety_delay(self) -> float:
        """Delay de seguranca/longo (segundos)."""
        lo, hi = self.SAFETY_DELAY_MS
        return self._rng.uniform(lo, hi) / 1000.0

    # -----------------------
    # Comportamentos especiais
    # -----------------------
    def maybe_extra_pause(self) -> float:
        """Retorna tempo extra de pausa com probabilidade PAUSE_PROB."""
        if self._rng.random() < self.PAUSE_PROB:
            lo, hi = self.PAUSE_EXTRA_MS
            return self._rng.uniform(lo, hi) / 1000.0
        return 0.0

    def error_recovery_delay(self) -> float:
        """Delay apos erro/falha (simula pensar antes de tentar de novo)."""
        lo, hi = self.ERROR_RECOVERY_MS
        return self._rng.uniform(lo, hi) / 1000.0

    # -----------------------
    # Movimento do mouse
    # -----------------------
    def human_mouse_move(
        self,
        page,
        target_x: float,
        target_y: float,
        steps: Optional[int] = None,
    ) -> None:
        """Move o mouse de forma humanizada ate (target_x, target_y).

        Usa movimento com aceleracao/desaceleracao (ease-in-out), possivel
        overshoot e jitter final.
        """
        try:
            pos = page.evaluate("() => ({ x: window.mouseX || 0, y: window.mouseY || 0 })")
            start_x = float(pos.get("x", target_x))
            start_y = float(pos.get("y", target_y))
        except Exception:
            start_x, start_y = target_x, target_y

        dx = target_x - start_x
        dy = target_y - start_y
        dist = (dx * dx + dy * dy) ** 0.5

        if dist < 5:
            page.mouse.move(
                target_x + self._rng.uniform(-self.JITTER_PX, self.JITTER_PX),
                target_y + self._rng.uniform(-self.JITTER_PX, self.JITTER_PX),
            )
            return

        speed = self._rng.uniform(*self.MOUSE_SPEED_PX_MS)  # px/s
        duration = max(0.15, dist / speed)
        if steps is None:
            steps = max(10, int(duration * 60))

        for i in range(steps + 1):
            t = i / steps
            eased = 3 * t * t - 2 * t * t * t

            ox = oy = 0.0
            if t > 0.85 and self._rng.random() < self.OVERSHOOT_PROB:
                angle = self._rng.uniform(0, 2 * math.pi)
                overshoot = self._rng.uniform(0, self.OVERSHOOT_MAX_PX)
                decay = (1 - t) * 0.7
                ox = overshoot * decay * math.cos(angle)
                oy = overshoot * decay * math.sin(angle)

            x = start_x + dx * eased + ox
            y = start_y + dy * eased + oy
            page.mouse.move(x, y)
            time.sleep(self._rng.uniform(0.001, 0.004))

        page.mouse.move(
            target_x + self._rng.uniform(-self.JITTER_PX, self.JITTER_PX),
            target_y + self._rng.uniform(-self.JITTER_PX, self.JITTER_PX),
        )

    def human_click(self, page, x: float, y: float) -> None:
        """Click humanizado: move, pausa micro, click, pausa micro."""
        self.human_mouse_move(page, x, y)
        time.sleep(self._rng.uniform(0.03, 0.08))
        page.mouse.click(x, y)
        time.sleep(self._rng.uniform(0.02, 0.06))

    # -----------------------
    # Sleep helpers
    # -----------------------
    def sleep(self, seconds: float) -> None:
        """Sleep com micro-jitter (+-10%)."""
        jitter = self._rng.uniform(-0.1, 0.1)
        time.sleep(max(0.01, seconds * (1 + jitter)))

    def sleep_base(self) -> None:
        self.sleep(self.base_delay())

    def sleep_click(self) -> None:
        self.sleep(self.click_delay())

    def sleep_round(self) -> None:
        self.sleep(self.round_delay())

    def sleep_safety(self) -> None:
        self.sleep(self.safety_delay())

    def sleep_error_recovery(self) -> None:
        self.sleep(self.error_recovery_delay())


# Instancia global padrao (seed baseado no tempo para variabilidade)
_default_humanizer = Humanizer(int(time.time() * 1000) % 2**32)


def get_humanizer() -> Humanizer:
    return _default_humanizer