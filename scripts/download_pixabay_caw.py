#!/usr/bin/env python3
"""Download Pixabay crow sound 410792 into app/static/muninn_caw.mp3."""
import sys
import urllib.request
from pathlib import Path

# From https://pixabay.com/sound-effects/nature-crow-sound-effect-no-copyright-410792/
URL = (
    "https://cdn.pixabay.com/download/audio/2025/09/26/audio_c93bab67b9.mp3"
    "?filename=poorartistt-crow-sound-effect-no-copyright-410792.mp3"
)
OUT = Path(__file__).resolve().parents[1] / "app" / "static" / "muninn_caw.mp3"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Muninn/1.0)",
    "Referer": "https://pixabay.com/",
}


def main() -> int:
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    OUT.write_bytes(data)
    print(f"Wrote {OUT} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
