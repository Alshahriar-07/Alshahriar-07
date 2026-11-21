"""
Small SVG toolkit shared by every card.

- embeds only the font faces a card uses
- re-subsets each face to the card's actual character set (fontTools)
- CSS keyframes for load-in motion, with automatic reduced-motion fallback
- `STATIC=1` produces genuinely static files (no animation CSS, no SMIL)
- SMIL count-up helpers that work inside GitHub's <img> sandbox
- pixel-accurate text measurement so headings can be fitted instead of clipped

No JavaScript, no external requests: every card is a single self-contained SVG.
"""
from __future__ import annotations

import base64
import hashlib
import html
import io
import os
import re
from functools import lru_cache

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
FONT_DIR = os.path.join(ROOT, "fonts")

MOTION = not bool(os.environ.get("STATIC"))

# ---- palette ---------------------------------------------------------------
BG = "#0a0a0b"
CARD = "#101012"
CARD_HI = "#151518"
INK = "#f4f2ee"
SOFT = "#b8b5af"
MUTED = "#7b7a7f"
FAINT = "#4b4a50"
RULE = "#242427"
RULE_HI = "#35353b"
ACCENT = "#d9c5a7"
BLACK = "#08080a"

# ---- fonts -----------------------------------------------------------------
FONT_SPECS = {
    "serif": ("Instrument Serif", "normal", 400, "serif-400.woff"),
    "serif-i": ("Instrument Serif", "italic", 400, "serif-italic.woff"),
    "sans": ("Geist", "normal", 400, "geist-400.woff"),
    "sans-6": ("Geist", "normal", 600, "geist-600.woff"),
    "mono": ("Geist Mono", "normal", 400, "geistmono-400.woff"),
}
FONT_STACK = {
    "serif": "'Instrument Serif', Georgia, 'Times New Roman', serif",
    "serif-i": "'Instrument Serif', Georgia, 'Times New Roman', serif",
    "sans": "Geist, system-ui, -apple-system, 'Segoe UI', sans-serif",
    "sans-6": "Geist, system-ui, -apple-system, 'Segoe UI', sans-serif",
    "mono": "'Geist Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
}

BASE_CSS = """
.r{opacity:0;animation:rise .9s cubic-bezier(.2,.7,.2,1) both}
.f{opacity:0;animation:fade .9s ease-out both}
.sl{opacity:0;animation:slide .9s cubic-bezier(.2,.7,.2,1) both}
.p{opacity:0;animation:pop .7s cubic-bezier(.2,.8,.2,1) both;transform-box:fill-box;transform-origin:center}
.g{transform:scaleY(0);transform-box:fill-box;transform-origin:bottom;animation:grow .8s cubic-bezier(.2,.8,.2,1) both}
.b{transform:scaleX(0);transform-box:fill-box;transform-origin:left;animation:growx .9s cubic-bezier(.2,.8,.2,1) both}
.dr{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1.1s cubic-bezier(.4,0,.2,1) both}
.bl{animation:blink 1.15s steps(1,end) infinite}
.pl{animation:pulse 2.8s ease-in-out infinite}
.nu{animation:nudge 2.8s ease-in-out infinite}
.sh{animation:sheen 1.4s cubic-bezier(.3,0,.2,1) both}
@keyframes rise{from{opacity:0;transform:translateY(15px)}to{opacity:1;transform:translateY(0)}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes slide{from{opacity:0;transform:translateX(-18px)}to{opacity:1;transform:translateX(0)}}
@keyframes pop{0%{opacity:0;transform:scale(.35)}70%{opacity:1;transform:scale(1.08)}100%{opacity:1;transform:scale(1)}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes growx{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes draw{to{stroke-dashoffset:0}}
@keyframes blink{0%,48%{opacity:1}49%,100%{opacity:0}}
@keyframes pulse{0%,100%{opacity:.4}50%{opacity:1}}
@keyframes nudge{0%,72%,100%{transform:translate(0,0)}80%{transform:translate(3px,-3px)}90%{transform:translate(3px,-3px)}}
@keyframes sheen{from{transform:translateX(-620px) skewX(-18deg)}to{transform:translateX(720px) skewX(-18deg)}}
@media (prefers-reduced-motion: reduce){
 .r,.f,.sl,.p,.g,.b,.dr,.sh{opacity:1!important;transform:none!important;stroke-dashoffset:0!important;animation:none!important}
 .bl,.pl,.nu{animation:none!important}
}
""".strip()


# ---- text helpers ----------------------------------------------------------
def esc(value) -> str:
    return html.escape(str(value), quote=False)


def attr(value) -> str:
    return html.escape(str(value), quote=True)


def d(seconds: float, extra: str = "") -> str:
    """Inline animation delay/extra style."""
    style = f"animation-delay:{seconds:.2f}s;{extra}".rstrip(";")
    return f' style="{style}"'


def ff(key: str, size: float, color: str = INK, weight=None, italic=False, anchor=None, extra: str = "") -> str:
    """Common text attributes. x/y are supplied by the caller."""
    attrs = [f'font-family="{FONT_STACK[key]}"', f'font-size="{size:g}"', f'fill="{color}"']
    if weight:
        attrs.append(f'font-weight="{weight}"')
    if italic:
        attrs.append('font-style="italic"')
    if anchor:
        attrs.append(f'text-anchor="{anchor}"')
    if extra:
        attrs.append(extra)
    return " ".join(attrs)


# ---- fonts: subset + embed -------------------------------------------------
@lru_cache(maxsize=1)
def _raw_fonts() -> dict[str, bytes]:
    out = {}
    for key, (_, _, _, filename) in FONT_SPECS.items():
        with open(os.path.join(FONT_DIR, filename), "rb") as fh:
            out[key] = fh.read()
    return out


@lru_cache(maxsize=1)
def _metrics() -> dict[str, tuple[dict, dict, int]]:
    """cmap + hmtx + unitsPerEm for each face, for measurement."""
    out = {}
    for key, (_, _, _, filename) in FONT_SPECS.items():
        f = TTFont(os.path.join(FONT_DIR, filename))
        cmap = f.getBestCmap()
        hmtx = f["hmtx"].metrics
        out[key] = (cmap, hmtx, f["head"].unitsPerEm)
    return out


def _visible_text(svg_body: str) -> str:
    """Rendered characters, plus digits/punctuation that dynamic values may add."""
    text = re.sub(r"<[^>]*>", " ", svg_body)
    text = html.unescape(text)
    return text + " 0123456789.,:+-/%()&"



@lru_cache(maxsize=256)
def _subset_font(key: str, chars: str) -> bytes:
    data = _raw_fonts()[key]
    opts = subset.Options()
    opts.flavor = "woff"
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.name_languages = ["*"]
    opts.notdef_outline = True
    opts.recalc_bounds = True
    font = subset.load_font(io.BytesIO(data), opts)
    sub = subset.Subsetter(options=opts)
    sub.populate(text=chars)
    sub.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def font_face_css(keys, body: str) -> str:
    chars = "".join(sorted(set(_visible_text(body))))
    rules = []
    for key in keys:
        family, style, weight, _ = FONT_SPECS[key]
        payload = base64.b64encode(_subset_font(key, chars)).decode("ascii")
        rules.append(
            "@font-face{font-family:'%s';font-style:%s;font-weight:%d;font-display:swap;"
            "src:url(data:font/woff;base64,%s) format('woff')}" % (family, style, weight, payload)
        )
    return "".join(rules)


def measure(text: str, key: str = "sans", size: float = 16) -> float:
    cmap, hmtx, upem = _metrics()[key]
    width = 0.0
    for ch in text:
        glyph = cmap.get(ord(ch))
        if glyph is None:
            width += 0.5 * upem
        else:
            width += hmtx[glyph][0]
    return width / upem * size


def fit_size(text: str, key: str, max_width: float, start: float, floor: float = 10) -> float:
    size = start
    while size > floor and measure(text, key, size) > max_width:
        size -= 0.5
    return round(size, 1)


def wrap_px(text: str, key: str, size: float, max_width: float) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if measure(candidate, key, size) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ---- building blocks -------------------------------------------------------
def svg_doc(width, height, body, label, fonts=None, pad_left=0, pad_right=0,
            pad_bottom=14, css="", bg=CARD, radius=16, stroke=RULE):
    """Wrap a card body. `width`/`height` are the card itself; padding makes gaps."""
    fonts = fonts or tuple(FONT_SPECS)
    total_w = width + pad_left + pad_right
    total_h = height + pad_bottom
    face_css = font_face_css(fonts, body)
    style = face_css + (BASE_CSS if MOTION else "") + css
    frame = ""
    if bg:
        frame = (
            f'<rect x="0.5" y="0.5" width="{width - 1:g}" height="{height - 1:g}" rx="{radius}" '
            f'fill="{bg}" stroke="{stroke}"/>'
        )
    # A barely-there top highlight gives the charcoal some depth without a gradient look.
    if bg:
        frame += (
            f'<path d="M{radius},0.5 H{width - radius}" stroke="#ffffff" stroke-opacity=".055" fill="none"/>'
        )
    out = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:g}" height="{total_h:g}" '
        f'viewBox="0 0 {total_w:g} {total_h:g}" role="img" aria-label="{attr(label)}">'
        f"<title>{esc(label)}</title>"
        f"<style>{style}</style>"
        f'<g transform="translate({pad_left:g} 0)">{frame}{body}</g>'
        f"</svg>"
    )
    return out


def rule(x1, y, x2, color=RULE, opacity=1.0, width=1):
    return f'<line x1="{x1:g}" y1="{y:g}" x2="{x2:g}" y2="{y:g}" stroke="{color}" stroke-opacity="{opacity:g}" stroke-width="{width:g}"/>'


def vrule(x, y1, y2, color=RULE, opacity=1.0):
    return f'<line x1="{x:g}" y1="{y1:g}" x2="{x:g}" y2="{y2:g}" stroke="{color}" stroke-opacity="{opacity:g}" stroke-width="1"/>'


def kicker(x, y, text, color=MUTED, size=10, spacing=1.5, delay=None, anchor="start"):
    style = d(delay) if delay is not None else ""
    return (
        f'<text class="sl"{style} x="{x:g}" y="{y:g}" {ff("mono", size, color, anchor=anchor)} '
        f'letter-spacing="{spacing:g}">{esc(text)}</text>'
    )


def heading(x, y, first, italic="", color=INK, size=34, max_width=800, delay=0.0):
    """Display heading, automatically fitted to the available width."""
    while size > 12 and measure(first, "serif", size) + measure(italic, "serif-i", size) > max_width:
        size -= 0.5
    size = round(size, 1)
    second = f'<tspan font-style="italic">{esc(italic)}</tspan>' if italic else ""
    return (
        f'<text class="r"{d(delay)} x="{x:g}" y="{y:g}" {ff("serif", size, color)} '
        f'letter-spacing="-0.4">{esc(first)}{second}</text>'
    )


def body_text(x, y, text, color=SOFT, size=13, delay=None, key="sans", anchor="start", extra=""):
    style = d(delay) if delay is not None else ""
    return (
        f'<text class="{("r" if delay is not None else "f")}"{style} x="{x:g}" y="{y:g}" '
        f'{ff(key, size, color, anchor=anchor, extra=extra)}>{esc(text)}</text>'
    )


def count_up(value, x, y, size, color=INK, begin=0.0, dur=0.9, weight=None,
             key="serif", anchor="start", decimals=0, bg=CARD):
    """SMIL count-up that can never hide its own result.

    The true value is always in the SVG. Animated frames are opaque-painted
    covers that sit above it for one frame each and then return to opacity 0,
    so if SMIL is disabled (or a renderer is mid-animation) the final number is
    still correct. This is more robust than opacity-only stacked frames.
    """
    final = f"{value:,.{decimals}f}"
    common = (
        f'x="{x:g}" y="{y:g}" font-family="{FONT_STACK[key]}" font-size="{size:g}" '
        f'fill="{color}" text-anchor="{anchor}"'
    )
    if weight:
        common += f' font-weight="{weight}"'
    final_text = f"<text {common}>{final}</text>"
    if not MOTION:
        return final_text

    width = measure(final, key, size) + 16
    if anchor == "end":
        left = x - width + 8
    elif anchor == "middle":
        left = x - width / 2
    else:
        left = x - 8
    top = y - size * 0.86
    height = size * 0.97
    frames = 14
    frame_dur = max(0.04, dur / frames)
    out = []
    for i in range(frames + 1):
        shown = final if i == frames else f"{value * (1 - (1 - i / frames) ** 3):,.{decimals}f}"
        on = begin + frame_dur * i
        out.append(
            f'<g opacity="0"><rect x="{left:.1f}" y="{top:.1f}" width="{width:.1f}" height="{height:.1f}" fill="{bg}"/>'
            f'<text {common}>{shown}</text>'
            f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.03;0.97;1" '
            f'dur="{frame_dur:.3f}s" begin="{on:.3f}s" fill="remove"/></g>'
        )
    return final_text + "".join(out)


def arrow(x, y, color=MUTED, size=13, delay=None, motion=True):
    """A small diagonal arrow, optionally nudged forever."""
    cls = "nu" if (motion and MOTION) else ""
    style = d(delay) if delay is not None else ""
    return (
        f'<text class="{cls}"{style} x="{x:g}" y="{y:g}" {ff("sans", size, color)}>↗</text>'
    )


def icon_box(x, y, size=34, color=SOFT):
    """Thin square with a small glyph inside, used by the profile tiles."""
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{size:g}" height="{size:g}" rx="8" fill="none" stroke="{RULE_HI}"/>'
    )


def project_icon(x, y, slug, color=SOFT):
    """Simple monochrome marks drawn from primitives. No logos, no external assets."""
    c = color
    s = f'stroke="{c}" stroke-width="1.3" fill="none" stroke-linecap="round" stroke-linejoin="round"'
    if slug == "seed-code-chat":
        return (f'<path d="M{x+3:g} {y+7:g} h18 a3 3 0 0 1 3 3 v8 a3 3 0 0 1 -3 3 h-9 l-6 5 v-5 h-3 a3 3 0 0 1 -3 -3 v-8 a3 3 0 0 1 3 -3 z" {s}/>'
                f'<path d="M{x+10:g} {y+14:g} h8" {s}/>')
    if slug == "seed-code-mail":
        return (f'<rect x="{x+2:g}" y="{y+4:g}" width="24" height="17" rx="2.5" {s}/>'
                f'<path d="M{x+3:g} {y+6:g} l11 8 11 -8" {s}/>')
    if slug == "mr-mesoff":
        return (f'<path d="M{x+4:g} {y+4:g} h20 v13 h-8 l-5 4 v-4 h-7 z" {s}/>'
                f'<path d="M{x+9:g} {y+10:g} h10" {s}/>')
    if slug == "seedcode-cli":
        return (f'<rect x="{x+2:g}" y="{y+3:g}" width="24" height="19" rx="3" {s}/>'
                f'<path d="M{x+7:g} {y+10:g} l4 4 -4 4 M{x+14:g} {y+18:g} h6" {s}/>')
    if slug == "intllm":
        return (f'<rect x="{x+6:g}" y="{y+3:g}" width="16" height="20" rx="3" {s}/>'
                f'<path d="M{x+10:g} {y+9:g} h8 M{x+10:g} {y+13:g} h8 M{x+10:g} {y+17:g} h5" {s}/>'
                f'<path d="M{x+2:g} {y+8:g} h2 M{x+2:g} {y+16:g} h2 M{x+24:g} {y+8:g} h2 M{x+24:g} {y+16:g} h2" {s}/>')
    if slug == "dorkey":
        return (f'<path d="M{x+4:g} {y+22:g} v-6 M{x+10:g} {y+22:g} v-11 M{x+16:g} {y+22:g} v-8 M{x+22:g} {y+22:g} v-15" {s}/>'
                f'<path d="M{x+3:g} {y+5:g} h6" {s}/>')
    return icon_box(x, y, 26, color)


def tile_icon(x, y, slug, color=SOFT):
    c = color
    if slug == "portfolio":
        return (f'<path d="M{x+3:g} {y+5:g} h24 v20 h-24 z" stroke="{c}" stroke-width="1.3" fill="none" stroke-linejoin="round"/>'
                f'<path d="M{x+6:g} {y+18:g} l5 -5 4 4 3 -3 6 6" stroke="{c}" stroke-width="1.3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
                f'<circle cx="{x+22:g}" cy="{y+11:g}" r="2" fill="{c}"/>')
    if slug == "linkedin":
        return (f'<rect x="{x+3:g}" y="{y+3:g}" width="24" height="24" rx="3" stroke="{c}" stroke-width="1.3" fill="none"/>'
                f'<path d="M{x+9:g} {y+12:g} v9 M{x+9:g} {y+8:g} v.1 M{x+14:g} {y+21:g} v-9 M{x+14:g} {y+15:g} c0-2 4-2.2 4 0 v6" stroke="{c}" stroke-width="1.5" fill="none" stroke-linecap="round"/>')
    if slug == "instagram":
        return (f'<rect x="{x+3:g}" y="{y+3:g}" width="24" height="24" rx="7" stroke="{c}" stroke-width="1.3" fill="none"/>'
                f'<circle cx="{x+15:g}" cy="{y+15:g}" r="6.1" stroke="{c}" stroke-width="1.3" fill="none"/>'
                f'<circle cx="{x+21.3:g}" cy="{y+8.7:g}" r="1.2" fill="{c}"/>')
    return ""
