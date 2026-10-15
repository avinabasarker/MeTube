"""Generate assets/icon.ico: purple rounded square with a white play triangle."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ICON_PATH = ROOT / "assets" / "icon.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)
PURPLE = (108, 92, 231, 255)
WHITE = (255, 255, 255, 255)


def render(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    radius = max(2, int(size * 0.22))
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=PURPLE)
    triangle = [
        (size * 0.40, size * 0.26),
        (size * 0.40, size * 0.74),
        (size * 0.76, size * 0.50),
    ]
    draw.polygon(triangle, fill=WHITE)
    return image


def main() -> int:
    ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    base = render(256)
    base.save(ICON_PATH, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"wrote {ICON_PATH} ({ICON_PATH.stat().st_size} bytes, sizes={list(SIZES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
