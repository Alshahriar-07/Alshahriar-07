#!/usr/bin/env python3
"""
Validate the generated cards and the README that references them.

Checks:
  - every SVG parses as XML
  - no scripts, event handlers, external images/fonts or remote CSS
  - images are embedded as data: URIs and fonts are embedded WOFF
  - every rendered glyph exists in an embedded face (no silent fallback)
  - required cards exist and README <img> paths resolve
  - contribution totals agree with the daily data
  - STATIC=1 output contains no animation; animated output does

Usage:
    python scripts/validate_output.py
    python scripts/validate_output.py --dir cards --data data/contributions.json --readme README.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from fontTools.ttLib import TTFont  # noqa: E402
from svg_kit import FONT_SPECS  # noqa: E402

NS = "{http://www.w3.org/2000/svg}"
REQUIRED = [
    "hero.svg", "portfolio.svg", "github.svg", "linkedin.svg", "about.svg",
    "monthly-activity.svg", "contribution-graph.svg", "title-work.svg",
    "projects/seed-code-chat.svg", "projects/seed-code-mail.svg", "projects/mr-mesoff.svg",
    "projects/seedcode-cli.svg", "projects/intllm.svg", "projects/dorkey.svg",
    "skills.svg", "experience.svg", "education.svg",
]
FAMILY_KEYS = {
    "Instrument Serif": ("serif", "serif-i"),
    "Geist": ("sans", "sans-6"),
    "Geist Mono": ("mono",),
}
PROJECT_URLS = [
    "https://seedcode-chat.vercel.app", "https://mrseedmail.vercel.app", "https://mrmesoff.vercel.app",
    "https://seedcode-cli.vercel.app", "https://intllm.vercel.app", "https://dorkey.vercel.app",
    "https://github.com/Alshahriar-07/seedcode-cli",
]


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _glyphs() -> dict:
    out = {}
    for key, (_, _, _, filename) in FONT_SPECS.items():
        font = TTFont(os.path.join(ROOT, "fonts", filename))
        cmap = set()
        for table in font["cmap"].tables:
            cmap |= set(table.cmap)
        out[key] = cmap
    return out


def _first_family(value: str) -> str:
    return value.split(",")[0].strip().strip("'\"")


def _walk_text(elem, inherited, glyphs, missing):
    family = elem.get("font-family", inherited)
    for child in elem:
        if _local(child.tag) == "text":
            _walk_text(child, family, glyphs, missing)
        else:
            _walk_text(child, family, glyphs, missing)
    if _local(elem.tag) == "text":
        content = "".join(elem.itertext())
        fam = _first_family(family) if family else "Geist"
        keys = FAMILY_KEYS.get(fam, ("sans",))
        available = set()
        for key in keys:
            available |= glyphs[key]
        for ch in content:
            if ch.isspace():
                continue
            if ord(ch) not in available:
                missing.add((fam, ch, f"U+{ord(ch):04X}"))


def validate_svg(path: str, glyphs, static, errors, warnings):
    rel = os.path.relpath(path, ROOT)
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        errors.append(f"{rel}: XML parse error: {exc}")
        return
    root = tree.getroot()
    if _local(root.tag) != "svg":
        errors.append(f"{rel}: root is not <svg>")
        return
    for attr in ("width", "height", "viewBox"):
        if not root.get(attr):
            errors.append(f"{rel}: missing {attr}")
    width = root.get("width", "0")
    height = root.get("height", "0")
    try:
        if float(width) <= 0 or float(height) <= 0:
            errors.append(f"{rel}: invalid dimensions {width}x{height}")
    except ValueError:
        errors.append(f"{rel}: non-numeric dimensions {width}x{height}")

    text = open(path, encoding="utf-8").read()
    if not root.get("aria-label"):
        errors.append(f"{rel}: missing aria-label")
    for bad in ("<script", "javascript:", "<foreignObject", "<iframe"):
        if bad.lower() in text.lower():
            errors.append(f"{rel}: contains forbidden {bad}")

    missing = set()
    for elem in root.iter():
        tag = _local(elem.tag)
        if tag == "script":
            errors.append(f"{rel}: contains <script>")
        if tag == "text":
            _walk_text(elem, elem.get("font-family"), glyphs, missing)
        for name, value in elem.attrib.items():
            lname = _local(name).lower()
            if lname.startswith("on"):
                errors.append(f"{rel}: event handler attribute {lname}")
            if lname in ("href", "src") or lname.endswith("href"):
                if value.startswith("http://") or value.startswith("https://"):
                    errors.append(f"{rel}: external resource in {lname}")
                if tag == "image" and not value.startswith("data:image/"):
                    errors.append(f"{rel}: <image> is not an embedded data: URI")
    for fam, ch, code in sorted(missing):
        errors.append(f"{rel}: glyph {code} '{ch}' missing from {fam}")

    style = " ".join(t.text or "" for t in root.iter(f"{NS}style"))
    if not style:
        errors.append(f"{rel}: no embedded <style>")
    else:
        if "@font-face" not in style:
            errors.append(f"{rel}: no @font-face")
        for url in re.findall(r"url\(([^)]+)\)", style):
            if not url.startswith("data:font/"):
                errors.append(f"{rel}: non-embedded CSS resource {url[:40]}")
        if "@import" in style:
            errors.append(f"{rel}: CSS @import is not allowed")
        has_anim = "animation:" in style or "<animate" in text or "<set " in text
        if static:
            if "@keyframes" in style or "animation:" in style:
                errors.append(f"{rel}: STATIC output still contains CSS animation")
            if re.search(r"<(animate|set|animateTransform)\b", text):
                errors.append(f"{rel}: STATIC output still contains SMIL animation")
        elif not has_anim:
            warnings.append(f"{rel}: animated output has no animation (check the card)")


def validate_readme(path: str, cards_dir: str, errors):
    if not path or not os.path.exists(path):
        return
    text = open(path, encoding="utf-8").read()
    readme_dir = os.path.dirname(os.path.abspath(path))
    for src in re.findall(r'<img[^>]+src="([^"]+)"', text):
        target = src[2:] if src.startswith("./") else src
        if target.startswith("http"):
            continue
        if not os.path.exists(os.path.join(readme_dir, target)):
            errors.append(f"README: missing image {src}")
    for url in PROJECT_URLS:
        if url not in text:
            errors.append(f"README: missing project link {url}")
    if "<script" in text:
        errors.append("README: contains a script tag")
    if "width=\"32.5%\"" not in text:
        errors.append("README: the three profile tiles are not at 32.5% width")


def validate_data(data, errors, warnings):
    try:
        total = sum(int(d["count"]) for d in data["days"])
        active = sum(1 for d in data["days"] if int(d["count"]) > 0)
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"data: malformed days ({exc})")
        return
    if total != int(data["total_contributions"]):
        errors.append(f"data: total {data['total_contributions']} != sum of days {total}")
    if active != int(data["active_days"]):
        errors.append(f"data: active days {data['active_days']} != counted {active}")
    if sum(int(m["total"]) for m in data["monthly"]) != total:
        errors.append("data: monthly totals do not add up to the yearly total")
    if data.get("sample"):
        warnings.append("data: SAMPLE FIXTURE (not real contribution data)")
    if data["best_day"]["count"] <= 0:
        errors.append("data: best day is zero")
    generated = data.get("generated_at", "")
    if not generated.endswith("Z"):
        warnings.append("data: generated_at is not an RFC3339 UTC timestamp")


def validate_dir(cards_dir, data, readme=None, static=None, quiet=False):
    errors, warnings = [], []
    glyphs = _glyphs()
    if not os.path.isdir(cards_dir):
        errors.append(f"missing output directory {cards_dir}")
    for rel in REQUIRED:
        path = os.path.join(cards_dir, rel)
        if not os.path.exists(path):
            errors.append(f"missing required card {rel}")
            continue
        validate_svg(path, glyphs, bool(static), errors, warnings)
    # Any extra SVG in cards/ is validated too.
    for base, _, files in os.walk(cards_dir):
        for name in files:
            if not name.endswith(".svg"):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, cards_dir).replace("\\", "/")
            if rel not in REQUIRED:
                validate_svg(path, glyphs, bool(static), errors, warnings)
    validate_data(data, errors, warnings)
    if readme:
        validate_readme(readme, cards_dir, errors)

    if data.get("sample"):
        activity = open(os.path.join(cards_dir, "monthly-activity.svg"), encoding="utf-8").read()
        heatmap = open(os.path.join(cards_dir, "contribution-graph.svg"), encoding="utf-8").read()
        if "SAMPLE DATA" not in activity or "SAMPLE DATA" not in heatmap:
            errors.append("sample fixture: cards are not visibly labeled SAMPLE DATA")
    else:
        for card in ("monthly-activity.svg", "contribution-graph.svg"):
            path = os.path.join(cards_dir, card)
            if os.path.exists(path) and "SAMPLE DATA" in open(path, encoding="utf-8").read():
                errors.append(f"{card}: real data is labeled SAMPLE DATA")

    count = len([1 for b, _, fs in os.walk(cards_dir) for f in fs if f.endswith(".svg")])
    if not quiet:
        print(f"validated {count} SVG cards")
        for warning in warnings:
            print(f"  warning: {warning}")
        for error in errors:
            print(f"  ERROR: {error}")
    if errors:
        print(f"{len(errors)} validation error(s)", file=sys.stderr)
        return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate generated profile cards")
    parser.add_argument("--dir", default=os.path.join(ROOT, "cards"))
    parser.add_argument("--data", default=os.path.join(ROOT, "data", "contributions.json"))
    parser.add_argument("--readme", default=os.path.join(ROOT, "README.md"))
    parser.add_argument("--static", action="store_true", help="expect static output")
    args = parser.parse_args(argv)

    with open(args.data, encoding="utf-8") as fh:
        data = json.load(fh)
    ok = validate_dir(args.dir, data, readme=args.readme, static=args.static)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
