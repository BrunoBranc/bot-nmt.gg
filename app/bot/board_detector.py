"""Visual, read-only first pass for the Power Blocks canvas.

The game is rendered on a canvas, so it has no DOM cells to inspect.  This
module proposes quiet screen regions from a canvas screenshot; it deliberately
does not click, drag, or call the game's APIs.
"""

from __future__ import annotations
from typing import Optional

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageStat


@dataclass(frozen=True)
class Candidate:
    x: int
    y: int
    score: float


class BoardDetector:
    """Find low-detail patches in the currently visible board area."""

    def create_preview(
        self,
        canvas_path: Path,
        report_dir: Path = Path("logs/diagnostics"),
        clearance: int = 18,
        target_size: Optional[tuple[int, int]] = None,
    ) -> tuple[Path, Path, list[Candidate]]:
        """Analisa o canvas e devolve candidatos (x, y) em espaco CSS.

        target_size: dimensoes (largura, altura) do canvas em pixels CSS.
        Se fornecido, a imagem e redimensionada para esse tamanho ANTES da
        deteccao, de modo que as coordenadas retornadas sejam diretamente
        somaveis a canvas_box.x / canvas_box.y pelo engine. Isso torna o
        detector independente do devicePixelRatio (DPI) da tela.
        """
        image = Image.open(canvas_path).convert("RGB")
        if target_size is not None:
            image = image.resize(target_size, Image.LANCZOS)
        candidates = self._find_candidates(image, clearance)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        preview_path = report_dir / f"board_preview_{stamp}.png"
        data_path = report_dir / f"board_preview_{stamp}.json"
        self._draw_preview(image, candidates).save(preview_path)
        data_path.write_text(json.dumps({
            "source_canvas": canvas_path.name,
            "target_size": list(target_size) if target_size else None,
            "analyzed_size": list(image.size),
            "mode": "read-only visual preview (CSS-space)",
            "warning": "Coordinates are screen-space suggestions, not placements.",
            "candidates": [candidate.__dict__ for candidate in candidates],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return preview_path, data_path, candidates

    @staticmethod
    def _find_candidates(image: Image.Image, clearance: int = 18) -> list[Candidate]:
        width, height = image.size
        # A barra lateral ocupa ~280 px independente do DPI. Como a imagem
        # agora esta em espaco CSS, esses limites sao validos para qualquer
        # resolucao de tela.
        left = min(max(300, round(width * 0.35)), max(0, width - 120))
        right = min(width - 10, left + round(height * 1.2))
        # Exclui a navegacao superior e o dock de figuras inferior.
        top = 70
        bottom = round(height * 0.55)
        # clear/patch/step sao derivados do tamanho (ja em CSS), entao
        # sao independentes da escala de tela.
        patch = max(clearance, round(min(width, height) * 0.03))
        step = max(12, patch // 2)
        ranked: list[Candidate] = []
        for y in range(top, bottom - patch, step):
            for x in range(left, right - patch, step):
                crop = image.crop((x, y, x + patch, y + patch))
                stat = ImageStat.Stat(crop)
                mean = sum(stat.mean) / 3
                deviation = sum(stat.var) / 3
                pixels = list(crop.getdata())
                bright_fraction = sum(1 for pixel in pixels if max(pixel) > 110) / len(pixels)
                if bright_fraction > 0.10:
                    continue
                ranked.append(Candidate(x + patch // 2, y + patch // 2, round(mean + deviation ** 0.5, 2)))

        ranked.sort(key=lambda item: item.score)
        selected: list[Candidate] = []
        # Distancia minima entre candidatos em pixels CSS (mesmo espaco da imagem).
        min_dist = max(36, round(min(width, height) * 0.07))
        for item in ranked:
            if all((item.x - other.x) ** 2 + (item.y - other.y) ** 2 >= min_dist ** 2 for other in selected):
                selected.append(item)
            if len(selected) == 12:
                break
        return selected

    @staticmethod
    def _draw_preview(image: Image.Image, candidates: list[Candidate]) -> Image.Image:
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        for index, candidate in enumerate(candidates, start=1):
            radius = 12
            draw.ellipse((candidate.x - radius, candidate.y - radius, candidate.x + radius, candidate.y + radius), outline="#00e5ff", width=3)
            draw.text((candidate.x + radius + 2, candidate.y - radius), str(index), fill="#00e5ff", stroke_width=1, stroke_fill="#001014")
        return annotated
