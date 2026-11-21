#!/usr/bin/env python3
"""
Prepare the real portrait in assets/ for the hero card.

The source photo is a black-and-white portrait on a transparent/white
background. This script composites it on white (so transparency never turns
black), takes a 4:5 head-and-shoulders crop that keeps the original framing and
appearance, resizes it for a retina-size hero frame, applies a light unsharp
mask, and writes a compact WebP.

The original photo is never modified. The generator calls this automatically if
the derived portrait is missing, and can be run by hand:

    python scripts/prep_portrait.py
    python scripts/prep_portrait.py assets/me.png assets/portrait.webp
"""
import os
import sys

from PIL import Image, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DEFAULT_SRC = os.path.join(ROOT, "assets", "me.png")
DEFAULT_OUT = os.path.join(ROOT, "assets", "portrait.webp")

# 4:5 crop around the face in the 1024x1024 source. Keeps the headphones,
# shoulders and the natural white space above the head.
CROP = (151, 120, 874, 1024)
OUT_W, OUT_H = 560, 700


def prepare(src=DEFAULT_SRC, out=DEFAULT_OUT):
    if not os.path.exists(src):
        raise FileNotFoundError(f"portrait source not found: {src}")

    im = Image.open(src)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        plate = Image.new("RGB", im.size, (255, 255, 255))
        plate.paste(im, mask=im.getchannel("A"))
        im = plate
    else:
        im = im.convert("RGB")

    gray = ImageOps.grayscale(im)

    # Only crop what is actually there; the source may already be cropped.
    box = (
        max(0, min(CROP[0], gray.width - 1)),
        max(0, min(CROP[1], gray.height - 1)),
        max(1, min(CROP[2], gray.width)),
        max(1, min(CROP[3], gray.height)),
    )
    gray = gray.crop(box)

    # Preserve the photo's own tonality, with a restrained contrast lift that
    # survives downscaling without changing how the subject looks.
    gray = ImageOps.autocontrast(gray, cutoff=0.5)
    gray = gray.resize((OUT_W, OUT_H), Image.Resampling.LANCZOS)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=1.2, percent=55, threshold=3))

    os.makedirs(os.path.dirname(out), exist_ok=True)
    gray.save(out, "WEBP", quality=86, method=6)
    size = os.path.getsize(out) / 1024
    print(f"wrote {os.path.relpath(out, ROOT)} ({OUT_W}x{OUT_H}, {size:.0f} KB)")
    return out


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    prepare(src, out)
