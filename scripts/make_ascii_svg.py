#!/usr/bin/env python3
"""
Render assets/me_ascii.svg - a genuine character portrait from assets/me.png.

The source is cropped around the head, headphones, raised hand and shoulders,
line-darkened (difference of Gaussians) so the eyes, brows, jaw and headphone
edges survive downsampling, then sampled onto a 180 x 96 character grid and
mapped through a monochrome density ramp. Every visible mark is a character;
the PNG is never embedded.

The output is only the character art: light ink on a fully transparent canvas,
with no background, frame, card, labels or margins. The hero card uses the same
rows against its own dark surface, so the portrait floats on the existing page
background. The asset is deliberately static so it always renders; the reveal
animation lives in the hero card.

    python scripts/make_ascii_svg.py
"""
from __future__ import annotations

import html
import os
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SRC = os.path.join(ROOT, "assets", "me.png")
OUT = os.path.join(ROOT, "assets", "me_ascii.svg")

# Square head-and-shoulders crop in the 1024 px source. Keeps the hair,
# both ear cups, the raised hand and the shirt without touching the original.
CROP = (62, 124, 962, 1024)

COLS, ROWS = 180, 96
RAMP = " .`:-=+*cs#%@"  # bright/blank -> dark/dense
WHITE_FLOOR = 0.80
GAMMA = 0.35
DOG_WEIGHT = 0.50
ALPHA_FLOOR = 110

INK = "#f4f2ee"  # light ink: the portrait is viewed on the dark profile surface
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

W, H = 750, 750
ART_W = ART_H = 750
ART_X, ART_Y = 0, 0
CELL_H = ART_H / ROWS


def _prepared_image() -> tuple[Image.Image, Image.Image]:
    im = Image.open(SRC).convert("RGBA")
    alpha = im.getchannel("A").crop(CROP)
    plate = Image.new("RGB", im.size, (255, 255, 255))
    plate.paste(im, mask=im.getchannel("A"))
    gray = plate.convert("L").crop(CROP)

    # Local line work: thin dark ridges are what make eyes and the jaw read.
    fine = gray.filter(ImageFilter.GaussianBlur(1.2))
    coarse = gray.filter(ImageFilter.GaussianBlur(6))
    lines = ImageChops.subtract(coarse, fine)
    lines = lines.point(lambda v: int(min(255, v * 1.4)))
    gray = ImageChops.subtract(gray, lines.point(lambda v: int(v * DOG_WEIGHT)))
    gray = ImageEnhance.Contrast(gray).enhance(1.05)
    return gray, alpha


def sample_rows() -> list[str]:
    gray, alpha = _prepared_image()
    gray = gray.resize((COLS, ROWS), Image.Resampling.LANCZOS)
    alpha = alpha.resize((COLS, ROWS), Image.Resampling.LANCZOS)
    gpx, apx = gray.load(), alpha.load()
    rows: list[str] = []
    for y in range(ROWS):
        line = []
        for x in range(COLS):
            lum = gpx[x, y] / 255.0
            if apx[x, y] < ALPHA_FLOOR or lum >= WHITE_FLOOR:
                line.append(" ")
                continue
            lum = lum ** GAMMA
            index = int((1.0 - lum) * (len(RAMP) - 1) + 0.5)
            line.append(RAMP[max(1, min(len(RAMP) - 1, index))])
        rows.append("".join(line))
    return rows


def build_svg(rows: list[str]) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'style="background:transparent" role="img" '
        f'aria-label="ASCII portrait of Al Shahriar Sowan, drawn with 180 by 96 monochrome characters on a transparent background.">',
        "<title>Al Shahriar Sowan - ASCII portrait</title>",
        '<g id="ascii-art">',
    ]

    # One text node per row. No background, border, label or container exists:
    # every visible mark is a character from the portrait.
    for i, line in enumerate(rows):
        baseline = ART_Y + i * CELL_H + CELL_H * 0.72
        parts.append(
            f'<text xml:space="preserve" x="{ART_X}" y="{baseline:.2f}" '
            f'font-family="{MONO}" font-size="{CELL_H * 0.86:.2f}" fill="{INK}" '
            f'fill-opacity=".95" stroke="{INK}" stroke-width=".05" '
            f'textLength="{ART_W}" lengthAdjust="spacing">{html.escape(line)}</text>'
        )
    parts.append('</g>')
    parts.append("</svg>")
    return "".join(parts)


def write_asset(rows: list[str]) -> str:
    svg = build_svg(rows)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)
    return svg


def load_rows() -> list[str]:
    """Rows from the generated asset; regenerate if it is missing or stale."""
    regenerate = not os.path.exists(OUT)
    if not regenerate and os.path.exists(SRC):
        regenerate = os.path.getmtime(SRC) > os.path.getmtime(OUT)
    if regenerate:
        write_asset(sample_rows())
    root = ET.parse(OUT).getroot()
    group = next((g for g in root.iter() if g.get("id") == "ascii-art"), None)
    if group is None:
        # The art rows are the only text nodes with a textLength, so this also
        # works with hand-edited SVGs.
        rows = [t.text or "" for t in root.iter() if t.get("textLength")]
    else:
        rows = [t.text or "" for t in group.iter() if t.tag.endswith("text")]
    if len(rows) != ROWS or any(len(row) != COLS for row in rows):
        write_asset(sample_rows())
        root = ET.parse(OUT).getroot()
        group = next((g for g in root.iter() if g.get("id") == "ascii-art"), None)
        rows = [t.text or "" for t in (group.iter() if group is not None else root.iter()) if t.tag.endswith("text")]
        rows = rows[:ROWS]
    return rows


def main() -> int:
    rows = sample_rows()
    write_asset(rows)
    size = os.path.getsize(OUT) / 1024
    print(f"wrote {os.path.relpath(OUT, ROOT)} ({size:.1f} KB, {COLS} x {ROWS} characters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
