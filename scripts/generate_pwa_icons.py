#!/usr/bin/env python3
"""Regenerate PWA icons from muninn_logo_transparent.png."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "app" / "static"
SRC = ROOT / "muninn_logo_transparent.png"
BG = (211, 84, 0, 255)  # --primary #d35400


def main() -> None:
    src = Image.open(SRC).convert("RGBA")
    for size in (192, 512):
        canvas = Image.new("RGBA", (size, size), BG)
        thumb = src.copy()
        thumb.thumbnail((int(size * 0.82), int(size * 0.82)), Image.Resampling.LANCZOS)
        ox = (size - thumb.width) // 2
        oy = (size - thumb.height) // 2
        canvas.paste(thumb, (ox, oy), thumb)
        out = ROOT / f"pwa-icon-{size}.png"
        canvas.convert("RGB").save(out, "PNG")
        print(out)


if __name__ == "__main__":
    main()
