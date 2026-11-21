#!/usr/bin/env python3
"""
Render the profile README cards from content.py + data/contributions.json.

    python generate_cards.py                 # animated cards/ + validation
    STATIC=1 python generate_cards.py        # static cards (no motion anywhere)
    python generate_cards.py --out build/x   # render elsewhere (tests)

Every card is a standalone SVG with embedded subset fonts and no JavaScript.
Contribution numbers come from data/contributions.json and are never invented;
if the feed is unavailable the fetch script keeps the previous data.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "scripts"))

import content as C  # noqa: E402
import make_ascii_svg as A  # noqa: E402
import svg_kit as K  # noqa: E402
from svg_kit import (  # noqa: E402
    ACCENT, BG, BLACK, CARD, CARD_HI, FAINT, INK, MUTED, RULE, RULE_HI, SOFT,
    arrow, body_text, count_up, d, esc, ff, heading, kicker, measure, rule,
    svg_doc, vrule,
)

W = 880
PAD = 44
RIGHT = W - PAD
ASCII_CSS = (
    ".aw{animation:asciiIn 1.25s cubic-bezier(.2,.8,.2,1) both}"
    "@keyframes asciiIn{0%{opacity:.25;clip-path:inset(0 0 100% 0)}25%{opacity:1}100%{opacity:1;clip-path:inset(0 0 0 0)}}"
    "@media (prefers-reduced-motion:reduce){.aw{opacity:1!important;clip-path:none!important;animation:none!important}}"
)
HEAT = ("#19191c", "#2c2c31", "#45454b", "#65656c", "#93939a", "#d5d2cb")
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")

ALL_FONTS = ("serif", "serif-i", "sans", "sans-6", "mono")


# ---- formatting ------------------------------------------------------------
def num(value) -> str:
    return f"{int(value):,}"


def mono_date(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%b %d, %Y").upper().replace(" 0", " ")


def short_date(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%b %d").upper().replace(" 0", " ")


def long_range(data) -> str:
    a = date.fromisoformat(data["range"]["from"])
    b = date.fromisoformat(data["range"]["to"])
    return f"{a.day:02d} {a.strftime('%b').upper()} {a.year} - {b.day:02d} {b.strftime('%b').upper()} {b.year}"


def cur_month_label(data) -> str:
    cm = data["current_month"]
    return f"{cm['label']} {cm['month'][:4]}"


def fit_lines(text, key, size, max_width, max_lines=2):
    """Shrink until the copy fits the slot, so no card ever clips a description."""
    while size > 9 and len(K.wrap_px(text, key, size, max_width)) > max_lines:
        size -= 0.2
    return round(size, 1), K.wrap_px(text, key, size, max_width)[:max_lines]


def ensure_fits(text, key, size, max_width, where):
    width = measure(text, key, size)
    if width > max_width + 0.5:
        raise AssertionError(f"{where}: '{text}' needs {width:.1f}px, only {max_width}px available")


# ---- shared furniture ------------------------------------------------------
def head(index, label, first, italic="", *, data=None, right="", y=88, size=34,
         max_width=700, delay=0.0, rule_y=108, sample_note=True):
    parts = [kicker(PAD, 45, f"{index} / {label}", delay=delay),
             heading(PAD, y, first, italic, size=size, max_width=max_width, delay=delay + 0.06)]
    if data is not None and data.get("sample") and sample_note:
        right = "SAMPLE DATA - NOT REAL"
    if right:
        color = ACCENT if (data is not None and data.get("sample")) else MUTED
        parts.append(
            f'<text class="f"{d(delay + 0.12)} x="{RIGHT}" y="45" {ff("mono", 8.5, color, anchor="end")} '
            f'letter-spacing="1.1">{esc(right)}</text>'
        )
    parts.append(rule(PAD, rule_y, RIGHT))
    return "".join(parts)


def fact(x, y, value, label, delay):
    return (
        f'<text class="p"{d(delay)} x="{x}" y="{y}" {ff("serif", 28, INK)} letter-spacing="-0.5">{value}</text>'
        f'<text class="f"{d(delay + 0.08)} x="{x}" y="{y + 19}" {ff("mono", 7.9, MUTED)} '
        f'letter-spacing="1.2">{label}</text>'
    )


def stat_cell(x, y, value, label, detail="", delay=0.0, value_size=25):
    out = [
        f'<text class="r"{d(delay)} x="{x}" y="{y}" {ff("serif", value_size, INK)} letter-spacing="-0.3">{esc(value)}</text>',
        f'<text class="f"{d(delay + 0.08)} x="{x}" y="{y + 17}" {ff("mono", 8.0, MUTED)} letter-spacing="1.05">{esc(label)}</text>',
    ]
    if detail:
        out.append(f'<text class="f"{d(delay + 0.12)} x="{x}" y="{y + 30}" {ff("mono", 7.6, MUTED)}>{esc(detail)}</text>')
    return "".join(out)


# ---- hero ------------------------------------------------------------------
def render_hero(data, ascii_rows):
    H = 430

    # The portrait is the same 180 x 96 character grid as assets/me_ascii.svg,
    # rendered as light ink directly on the card. No panel, frame, border or
    # label is drawn around it; the character gaps show the existing surface.
    cell_h = 322 / len(ascii_rows)
    art = ['<g class="aw" style="animation-delay:0.52s">']
    for i, line in enumerate(ascii_rows):
        baseline = 66 + i * cell_h + cell_h * 0.72
        art.append(
            f'<text xml:space="preserve" x="506" y="{baseline:.2f}" '
            f'{ff("mono", round(cell_h * 0.86, 2), INK)} fill-opacity=".95" '
            f'stroke="{INK}" stroke-width=".08" textLength="322" lengthAdjust="spacing">{esc(line)}</text>'
        )
    art.append('</g>')
    frame = ["".join(art)]

    left = [
        kicker(PAD, 46, "EAGOX STUDIO / INDEPENDENT SOFTWARE", delay=0.05),
        f'<text class="f"{d(0.10)} x="{RIGHT}" y="46" {ff("mono", 8.5, MUTED)} letter-spacing="1.1" text-anchor="end">GAZIPUR, BD / UTC+6</text>',
        f'<text class="r"{d(0.16)} x="{PAD}" y="140" {ff("serif", 96, INK)} letter-spacing="-1.6">Al Shahriar</text>',
        f'<text class="r"{d(0.28)} x="{PAD}" y="220" {ff("serif", 96, ACCENT)} font-style="italic" letter-spacing="-1.2">Sowan</text>',
        f'<text class="r"{d(0.42)} x="{PAD}" y="254" {ff("sans", 16.5, SOFT)}>Jr. Software &amp; AI Integration Developer</text>',
        f'<rect class="p"{d(0.50)} x="{PAD}" y="267" width="5" height="5" fill="{ACCENT}"/>',
        f'<text class="r"{d(0.50)} x="{PAD + 13}" y="276" {ff("sans", 13, SOFT)}>Founder of EAGOX Studio</text>',
        f'<text class="sl"{d(0.58)} x="{PAD}" y="311" {ff("mono", 10.1, ACCENT)} letter-spacing="1.35">Building Software. Integrating AI. Shipping Products.</text>',
        f'<line class="b"{d(0.68)} x1="{PAD}" y1="331" x2="{RIGHT - 276}" y2="331" stroke="{RULE}"/>',
        fact(PAD, 366, C.FACTS[0][0], C.FACTS[0][1], 0.78),
        fact(200, 366, C.FACTS[1][0], C.FACTS[1][1], 0.86),
        fact(356, 366, C.FACTS[2][0], C.FACTS[2][1], 0.94),
        vrule(180, 348, 388, RULE),
        vrule(336, 348, 388, RULE),
        f'<text class="f"{d(1.05)} x="{PAD}" y="412" {ff("mono", 8.6, MUTED)} letter-spacing=".4">alshahriarsayon.vercel.app</text>',
        arrow(176, 412, MUTED, 10, delay=1.1),
        vrule(478, 58, 396, RULE),
    ]
    ensure_fits(C.IDENTITY["title"], "sans", 16.5, 436, "hero title")
    ensure_fits(C.IDENTITY["tagline"], "mono", 10.1, 436, "hero tagline")
    ensure_fits(C.IDENTITY["name_lines"][0], "serif", 96, 436, "hero name")
    body = "".join(left + frame)
    label = (f'{C.IDENTITY["name"]} - {C.IDENTITY["title"]}. Founder of EAGOX Studio. '
             "ASCII portrait, location, flagship version and headline product facts.")
    return svg_doc(W, H, body, label, fonts=("serif", "serif-i", "sans", "mono"),
                   css=ASCII_CSS if K.MOTION else "", pad_bottom=14)


# ---- profile tiles ---------------------------------------------------------
def render_tile(tile, delay):
    H = 196
    cw = W / 3 - 8
    body = [
        f'<line class="b"{d(delay)} x1="22" y1=".8" x2="{cw - 22}" y2=".8" stroke="{ACCENT}" stroke-opacity=".45"/>',
        f'<text class="f"{d(delay + 0.04)} x="22" y="34" {ff("mono", 8.8, MUTED)} letter-spacing="1.3">{tile["index"]}</text>',
        f'<g class="f"{d(delay + 0.12)}>',
        K.icon_box(cw - 55, 20, 33, RULE_HI),
        K.tile_icon(cw - 51, 24, tile["slug"], SOFT),
        '</g>',
        f'<text class="r"{d(delay + 0.08)} x="22" y="104" {ff("serif", 30, INK)} letter-spacing="-0.6">{esc(tile["label"])}</text>',
        f'<text class="f"{d(delay + 0.16)} x="22" y="132" {ff("sans", 11.6, SOFT)}>{esc(tile["blurb"])}</text>',
        f'<line class="f"{d(delay + 0.2)} x1="22" y1="151" x2="{cw - 22}" y2="151" stroke="{RULE}"/>',
        f'<text class="f"{d(delay + 0.24)} x="22" y="176" {ff("mono", 8.2, MUTED)} letter-spacing=".3">{esc(tile["display"])}</text>',
        arrow(cw - 24, 178, ACCENT, 11.5, delay=delay + 0.3),
    ]
    ensure_fits(tile["label"], "serif", 30, cw - 110, "tile label")
    ensure_fits(tile["blurb"], "sans", 11.6, cw - 44, "tile blurb")
    ensure_fits(tile["display"], "mono", 8.2, cw - 66, "tile url")
    label = f'{tile["label"]} - {tile["url"]}'
    return svg_doc(cw, H, "".join(body), label,
                   fonts=("serif", "sans", "mono"), pad_left=4, pad_right=4, pad_bottom=14)


# ---- about -----------------------------------------------------------------
def render_about(data):
    H = 400
    head_html = head("01", "ABOUT", "Independent, ", "by design", data=data,
                     right="SOFTWARE · AI · PRODUCT")
    panel = [
        f'<rect x="44" y="126" width="540" height="246" rx="10" fill="#0c0c0e" stroke="{RULE}"/>',
        f'<circle cx="62" cy="145" r="3" fill="{ACCENT}" fill-opacity=".8"/>',
        f'<circle cx="74" cy="145" r="3" fill="{RULE_HI}"/>',
        f'<circle cx="86" cy="145" r="3" fill="{RULE_HI}"/>',
        f'<text x="314" y="148" {ff("mono", 7.8, FAINT)} text-anchor="middle" letter-spacing=".8">al@eagox: ~/studio</text>',
        f'<line x1="44" y1="158" x2="584" y2="158" stroke="{RULE}"/>',
    ]
    for i, (prompt, text) in enumerate(C.ABOUT_TERMINAL):
        y = 182 + i * 18.2
        delay = 0.18 + i * 0.07
        if prompt == "$":
            panel.append(f'<text class="f"{d(delay)} x="60" y="{y:.1f}" {ff("mono", 10.7, ACCENT)}>$</text>')
            panel.append(f'<text class="f"{d(delay)} x="76" y="{y:.1f}" {ff("mono", 10.7, INK)}>{esc(text)}</text>')
        else:
            panel.append(f'<text class="f"{d(delay)} x="76" y="{y:.1f}" {ff("mono", 10.7, SOFT)}>{esc(text)}</text>')
        ensure_fits(text, "mono", 10.7, 496, f"terminal line {i}")
    cursor_y = 182 + 10 * 18.2 - 2
    panel.append(f'<text class="f"{d(0.9)} x="60" y="{cursor_y:.1f}" {ff("mono", 10.7, ACCENT)}>$</text>')
    if K.MOTION:
        panel.append(f'<rect class="bl" x="78" y="{cursor_y - 10:.1f}" width="6.5" height="12" fill="{SOFT}" opacity=".55"/>')
    else:
        panel.append(f'<rect x="78" y="{cursor_y - 10:.1f}" width="6.5" height="12" fill="{SOFT}" opacity=".55"/>')

    rail = [
        f'<text class="f" x="608" y="146" {ff("mono", 8.4, MUTED)} letter-spacing="1.4">AT A GLANCE</text>',
    ]
    for i, (label, value) in enumerate(C.ABOUT_RAIL):
        y = 180 + i * 40
        rail.append(f'<text class="f"{d(0.3 + i * 0.06)} x="608" y="{y}" {ff("mono", 8.0, MUTED)} letter-spacing="1.2">{esc(label)}</text>')
        rail.append(f'<text class="f"{d(0.34 + i * 0.06)} x="608" y="{y + 17}" {ff("sans", 12.2, SOFT)}>{esc(value)}</text>')
        ensure_fits(value, "sans", 12.2, 228, f"about rail {label}")
    rail.append(vrule(588, 126, 364, RULE))

    label = ("About Al Shahriar Sowan - independent developer at EAGOX Studio. "
             "Builds web, desktop, Android and CLI products and integrates AI into them.")
    body = head_html + "".join(panel + rail)
    return svg_doc(W, H, body, label, fonts=("serif", "serif-i", "sans", "mono"))


# ---- monthly activity ------------------------------------------------------
def render_activity(data):
    H = 422
    cm = data["current_month"]
    months = data["monthly"]
    total = data["total_contributions"]
    peak = max(months, key=lambda m: m["total"])
    peak_idx = months.index(peak)
    cur_idx = len(months) - 1
    best = cm["best_day"]
    trend = cm.get("trend_pct")
    trend_note = "NO PRIOR DATA" if trend is None else f"{trend:+d}% VS {cm.get('trend_basis') or 'PREVIOUS MONTH'}"
    partial = " (TO DATE)" if cm.get("partial") else ""
    first_partial = date.fromisoformat(data["range"]["from"]).day != 1
    if first_partial and cm.get("partial"):
        partial_note = "THE FIRST AND CURRENT MONTHS ARE PARTIAL"
    elif first_partial:
        partial_note = "THE FIRST MONTH IS PARTIAL"
    elif cm.get("partial"):
        partial_note = "THE CURRENT MONTH IS PARTIAL"
    else:
        partial_note = ""

    head_html = head("02", "ACTIVITY", "The year in ", "commits", data=data,
                     right=f'{months[0]["label"]} {months[0]["month"][:4]} - {months[-1]["label"]} {months[-1]["month"][:4]}')

    left = [
        f'<text class="f"{d(0.14)} x="{PAD}" y="132" {ff("mono", 8.5, MUTED)} letter-spacing="1.3">CONTRIBUTIONS</text>',
        count_up(total, PAD, 194, 66, INK, begin=0.04, dur=1.05),
        f'<text class="f"{d(0.3)} x="{PAD}" y="214" {ff("mono", 8.1, MUTED)} letter-spacing=".5">{long_range(data)}</text>',
        f'<line class="b"{d(0.36)} x1="{PAD}" y1="236" x2="320" y2="236" stroke="{RULE}"/>',
        f'<text class="f"{d(0.42)} x="{PAD}" y="256" {ff("mono", 8.4, ACCENT)} letter-spacing="1.15">THIS MONTH · {cur_month_label(data)}{partial}</text>',
        f'<text class="r"{d(0.46)} x="{PAD}" y="291" {ff("serif", 34, INK)} letter-spacing="-0.4">{num(cm["total"])}'
        f'<tspan {ff("sans", 11, MUTED)}> contributions</tspan></text>',
        f'<text class="f"{d(0.52)} x="{PAD}" y="313" {ff("mono", 8.3, MUTED)}>{cm["active_days"]} active days · best {best["count"]} on {short_date(best["date"])}</text>',
        f'<text class="f"{d(0.58)} x="{PAD}" y="331" {ff("mono", 8.4, SOFT)}>Trend <tspan fill="{ACCENT if (trend or 0) >= 0 else SOFT}">{esc(trend_note)}</tspan></text>',
    ]

    # chart
    x0, x1 = 348, 832
    base_y = 252
    chart_top = 136
    step = (x1 - x0) / len(months)
    bw = min(21, step - 15)
    max_total = max(1, max(m["total"] for m in months))
    chart = [
        f'<text class="f" x="{x1}" y="124" {ff("mono", 8.0, SOFT)} text-anchor="end">PEAK {peak["total"]} · {peak["label"]} {peak["month"][:4]}</text>',
    ]
    if partial_note:
        chart.append(f'<text class="f" x="{x0}" y="302" {ff("mono", 7.2, MUTED)} letter-spacing=".4">{partial_note}</text>')
    for level in (0.25, 0.5, 0.75):
        gy = base_y - 116 * level
        chart.append(f'<line x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}" stroke="{RULE}" stroke-opacity=".55" stroke-dasharray="2 5"/>')
    chart.append(f'<line x1="{x0}" y1="{base_y}" x2="{x1}" y2="{base_y}" stroke="{RULE_HI}"/>')

    for i, month in enumerate(months):
        h = max(2.5, 116 * month["total"] / max_total)
        bx = x0 + i * step + (step - bw) / 2
        color = ACCENT if i == cur_idx else INK
        opacity = "1" if i in (cur_idx, peak_idx) else ".55"
        delay = 0.30 + i * 0.035
        chart.append(
            f'<rect class="g"{d(delay)} x="{bx:.1f}" y="{base_y - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="2" '
            f'fill="{color}" fill-opacity="{opacity}"/>'
        )
        chart.append(f'<text class="f"{d(delay + 0.05)} x="{bx + bw / 2:.1f}" y="270" {ff("mono", 7.7, MUTED)} text-anchor="middle" letter-spacing=".5">{month["label"]}</text>')
        if i == peak_idx:
            chart.append(f'<text class="f"{d(delay + 0.1)} x="{bx + bw / 2:.1f}" y="{base_y - h - 7:.1f}" {ff("mono", 7.6, INK)} text-anchor="middle">{month["total"]}</text>')
        elif i == cur_idx:
            chart.append(f'<text class="f"{d(delay + 0.1)} x="{bx + bw / 2:.1f}" y="{base_y - h - 7:.1f}" {ff("mono", 7.6, ACCENT)} text-anchor="middle">{month["total"]}</text>')

    # year boundary
    year_start = next((i for i, m in enumerate(months) if m["month"][:4] != months[0]["month"][:4]), None)
    if year_start:
        bx = x0 + year_start * step
        chart.append(f'<line x1="{bx:.1f}" y1="{chart_top}" x2="{bx:.1f}" y2="278" stroke="{RULE_HI}" stroke-dasharray="2 4"/>')
        chart.append(f'<text class="f" x="{x0 + year_start * step / 2:.1f}" y="286" {ff("mono", 7.0, FAINT)} text-anchor="middle">{months[0]["month"][:4]}</text>')
        chart.append(f'<text class="f" x="{(bx + x1) / 2:.1f}" y="286" {ff("mono", 7.0, FAINT)} text-anchor="middle">{months[-1]["month"][:4]}</text>')

    # footer stats
    stats = [
        ("CURRENT STREAK", str(data["current_streak"]), "CONSECUTIVE DAYS", 0.55),
        ("LONGEST STREAK", str(data["longest_streak"]), "DAYS", 0.62),
        ("ACTIVE DAYS", str(data["active_days"]), f'OF {data["tracked_days"]}', 0.69),
        ("BUSIEST DAY", str(data["best_day"]["count"]), mono_date(data["best_day"]["date"]), 0.76),
    ]
    footer = [f'<line class="f"{d(0.5)} x1="{PAD}" y1="348" x2="{RIGHT}" y2="348" stroke="{RULE}"/>']
    for i, (label, value, detail, delay) in enumerate(stats):
        x = PAD + i * 200
        footer.append(stat_cell(x, 378, value, label, detail, delay))
        if i:
            footer.append(vrule(x - 20, 362, 400, RULE))

    label = (f'{num(total)} GitHub contributions in the last year, {data["active_days"]} active days, '
             f'{data["current_streak"]}-day current streak, {data["longest_streak"]}-day longest streak.')
    body = head_html + "".join(left + chart + footer)
    return svg_doc(W, H, body, label, fonts=("serif", "serif-i", "sans", "mono"))


# ---- contribution heatmap --------------------------------------------------
def render_heatmap(data):
    H = 364
    days = data["days"]
    parsed = [(date.fromisoformat(item["date"]), int(item["count"]), int(item["level"])) for item in days]
    parsed.sort()
    first, last = parsed[0][0], parsed[-1][0]
    grid_start = first - timedelta(days=(first.weekday() + 1) % 7)  # Sunday
    cols = (last - grid_start).days // 7 + 1
    step, cell = 14.9, 12.0
    x0, y0 = 44, 146
    end_x = x0 + (cols - 1) * step + cell

    head_html = head("03", "CONTRIBUTIONS", "Every day, ", "accounted for", data=data,
                     right=f'UTC+6 · UPDATED {mono_date(data["range"]["to"])}')

    grid = []
    labels_done = False
    last_label_col = -10
    for col in range(cols):
        week_day = grid_start + timedelta(days=col * 7)
        new_month = col == 0 or week_day.month != (week_day - timedelta(days=7)).month
        if new_month and col - last_label_col >= 3:
            grid.append(f'<text class="f"{d(0.12)} x="{x0 + col * step:.1f}" y="134" {ff("mono", 7.8, MUTED)} letter-spacing=".6">{MONTHS[week_day.month - 1]}</text>')
            last_label_col = col

    for name, row in (("MON", 1), ("WED", 3), ("FRI", 5)):
        grid.append(f'<text class="f" x="{x0 - 8}" y="{y0 + row * step + 9:.1f}" {ff("mono", 7.2, MUTED)} text-anchor="end">{name}</text>')

    for day, count, level in parsed:
        offset = (day - grid_start).days
        col, row = divmod(offset, 7)
        x = x0 + col * step
        y = y0 + row * step
        delay = 0.16 + col * 0.012 + row * 0.004
        outline = ""
        if day == last:
            outline = f' stroke="{INK}" stroke-opacity=".55" stroke-width="1"'
        grid.append(
            f'<rect class="f"{d(delay)} x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="2.2" '
            f'fill="{HEAT[level]}"{outline}/>'
        )

    legend = [
        f'<text class="f" x="648" y="270" {ff("mono", 7.3, MUTED)} letter-spacing=".7">LESS</text>',
    ]
    for i, color in enumerate(HEAT):
        legend.append(f'<rect x="{680 + i * 13}" y="262" width="9" height="9" rx="1.8" fill="{color}"/>')
    legend.append(f'<text class="f" x="{680 + 6 * 13 + 4}" y="270" {ff("mono", 7.3, MUTED)} letter-spacing=".7">MORE</text>')

    footer = [f'<line class="f" x1="{PAD}" y1="292" x2="{RIGHT}" y2="292" stroke="{RULE}"/>']
    counts = [
        ("TOTAL", num(data["total_contributions"]), f'{data["tracked_days"]} DAYS', 0.45),
        ("ACTIVE DAYS", str(data["active_days"]), "WITH A COMMIT", 0.51),
        ("CURRENT STREAK", str(data["current_streak"]), "DAYS", 0.57),
        ("LONGEST STREAK", str(data["longest_streak"]), "DAYS", 0.63),
        ("BUSIEST DAY", str(data["best_day"]["count"]), mono_date(data["best_day"]["date"]), 0.69),
    ]
    for i, (label, value, detail, delay) in enumerate(counts):
        x = PAD + i * 158
        footer.append(stat_cell(x, 324, value, label, detail, delay, value_size=22))
        if i:
            footer.append(vrule(x - 18, 306, 338, RULE))

    label = (f'Contribution heatmap, {data["range"]["from"]} to {data["range"]["to"]}: '
             f'{num(data["total_contributions"])} contributions across {data["active_days"]} active days.')
    body = head_html + "".join(grid + legend + footer)
    return svg_doc(W, H, body, label, fonts=("serif", "serif-i", "mono"))


# ---- work title + projects -------------------------------------------------
def render_work_title():
    H = 96
    body = [
        kicker(PAD, 36, "04 / SELECTED WORK", delay=0.05),
        heading(PAD, 80, "SeedCode CLI, ", "and the work around it", size=31, max_width=700, delay=0.1),
        f'<text class="f"{d(0.16)} x="{RIGHT}" y="36" {ff("mono", 8.4, MUTED)} text-anchor="end" letter-spacing="1.1">01 FLAGSHIP · 05 MORE</text>',
    ]
    return svg_doc(W, H, "".join(body), "Selected work led by SeedCode CLI, the flagship AI coding agent, followed by five more products.", fonts=("serif", "serif-i", "mono"))


def render_subsection(label, right):
    """A slim section rail: used to separate the product suite from experiments."""
    H = 76
    body = [
        kicker(PAD, 36, label, color=ACCENT, delay=0.05),
        f'<text class="f"{d(0.12)} x="{RIGHT}" y="36" {ff("mono", 8.4, MUTED)} text-anchor="end" letter-spacing="1.1">{esc(right)}</text>',
        f'<line class="b"{d(0.18)} x1="{PAD}" y1="52" x2="{RIGHT}" y2="52" stroke="{RULE}"/>',
    ]
    return svg_doc(W, H, "".join(body), f"{label} section: {right.lower()}.", fonts=("mono",), pad_bottom=14)


def render_featured(project):
    """Full-width flagship showcase for SeedCode CLI."""
    H = 450
    title_size = K.fit_size(project["name"], "serif", 430, 64, 46)
    desc_size, desc_lines = fit_lines(project["desc"], "sans", 12.8, 430, 3)
    body = [
        kicker(PAD, 45, "01 / FLAGSHIP PROJECT", color=ACCENT, delay=0.05),
        f'<text class="f"{d(0.10)} x="{RIGHT}" y="45" {ff("mono", 8.5, MUTED)} text-anchor="end" letter-spacing="1.1">SEEDCODE CLI · {esc(project["version"])}</text>',
        f'<line class="b"{d(0.14)} x1="{PAD}" y1="64" x2="{RIGHT}" y2="64" stroke="{RULE}"/>',
        f'<text class="r"{d(0.18)} x="{PAD}" y="122" {ff("serif", title_size, INK)} letter-spacing="-1.2">{esc(project["name"])}</text>',
        f'<text class="f"{d(0.24)} x="{PAD}" y="148" {ff("mono", 9.2, ACCENT)} letter-spacing="1.6">AI CODING AGENT FOR THE TERMINAL</text>',
    ]
    for i, line in enumerate(desc_lines):
        body.append(f'<text class="f"{d(0.28 + i * 0.04)} x="{PAD}" y="{176 + i * 17.5:.1f}" {ff("sans", desc_size, SOFT)}>{esc(line)}</text>')

    for i, (label, detail) in enumerate(project["features"]):
        col, row = i % 2, i // 2
        x, y = PAD + col * 214, 234 + row * 46
        body.append(f'<rect class="p"{d(0.36 + row * 0.04)} x="{x}" y="{y - 7}" width="4" height="4" fill="{ACCENT}"/>')
        body.append(f'<text class="f"{d(0.38 + row * 0.04)} x="{x + 10}" y="{y}" {ff("mono", 8.0, INK)} letter-spacing=".9">{esc(label)}</text>')
        detail_lines = K.wrap_px(detail, "sans", 10.2, 192)
        for j, detail_line in enumerate(detail_lines[:2]):
            body.append(f'<text class="f"{d(0.40 + j * 0.03 + row * 0.04)} x="{x + 10}" y="{y + 15 + j * 11.5:.1f}" {ff("sans", 10.2, MUTED)}>{esc(detail_line)}</text>')

    body.append(f'<text class="f"{d(0.52)} x="{PAD}" y="340" {ff("mono", 8.2, ACCENT)} letter-spacing="1.1">{esc(project["platforms"])}</text>')
    body.append(f'<text class="f"{d(0.55)} x="{PAD}" y="356" {ff("mono", 7.8, MUTED)} letter-spacing=".8">{esc(project["tech"])}</text>')

    panel = [
        f'<rect class="f"{d(0.20)} x="496" y="80" width="340" height="254" rx="9" fill="#0c0c0e" stroke="{RULE}"/>',
        f'<line x1="496" y1="112" x2="836" y2="112" stroke="{RULE}"/>',
        f'<circle cx="514" cy="96" r="2.5" fill="{ACCENT}" fill-opacity=".8"/>',
        f'<circle cx="524" cy="96" r="2.5" fill="{RULE_HI}"/>',
        f'<circle cx="534" cy="96" r="2.5" fill="{RULE_HI}"/>',
        f'<text x="550" y="100" {ff("mono", 7.6, FAINT)} letter-spacing=".6">seedcode / workspace agent</text>',
        f'<text x="822" y="100" {ff("mono", 7.2, MUTED)} text-anchor="end" letter-spacing=".8">READY</text>',
        f'<circle cx="830" cy="97" r="2" fill="{ACCENT}"/>',
    ]
    terminal_lines = [
        ("$", "seedcode", ACCENT, INK),
        (">", "read README.md", MUTED, SOFT),
        ("+", "read README.md", ACCENT, SOFT),
        (">", "pytest -q", MUTED, SOFT),
        ("+", "tests passed · exit 0", ACCENT, SOFT),
        (">", "edit app.py", MUTED, SOFT),
        ("+", "updated app.py · +12 -5", ACCENT, SOFT),
    ]
    for i, (prefix, line, prefix_color, line_color) in enumerate(terminal_lines):
        y = 140 + i * 18
        panel.append(f'<text class="f"{d(0.34 + i * 0.015)} x="514" y="{y}" {ff("mono", 8.2, prefix_color)}>{prefix}</text>')
        panel.append(f'<text class="f"{d(0.35 + i * 0.015)} x="528" y="{y}" {ff("mono", 8.2, line_color)}>{esc(line)}</text>')
    panel.append(f'<text class="f"{d(0.5)} x="514" y="280" {ff("mono", 7.2, FAINT)}>workspace ~/projects/app</text>')
    panel.append(f'<text class="f"{d(0.54)} x="514" y="296" {ff("mono", 7.2, FAINT)}>local + cloud · 27 tools</text>')
    panel.append(f'<text class="f"{d(0.58)} x="514" y="312" {ff("mono", 7.2, ACCENT)}>evidence, not claims</text>')
    panel.append(f'<text class="f"{d(0.66)} x="496" y="348" {ff("mono", 7.2, FAINT)} letter-spacing=".5">REAL FILES · REAL COMMANDS · REAL RESULTS</text>')
    body.extend(panel)

    body.append(f'<line class="b"{d(0.62)} x1="{PAD}" y1="366" x2="{RIGHT}" y2="366" stroke="{RULE}"/>')
    stat_x = (PAD, 240, 400, 580)
    stat_sizes = (22, 22, 22, 20)
    for i, (value, label) in enumerate(project["stats"]):
        body.append(stat_cell(stat_x[i], 398, value, label, delay=0.64 + i * 0.04, value_size=stat_sizes[i]))
        if i:
            body.append(vrule(stat_x[i] - 20, 380, 424, RULE))

    web = project["live"].replace("https://", "").rstrip("/")
    repo = project["repo"].replace("https://", "")
    body.append(f'<text class="f"{d(0.86)} x="{PAD}" y="440" {ff("mono", 8.8, ACCENT)} letter-spacing=".3">{web} ↗</text>')
    body.append(f'<text class="f"{d(0.9)} x="{RIGHT}" y="440" {ff("mono", 7.8, SOFT)} text-anchor="end">{repo} ↗</text>')

    ensure_fits(project["name"], "serif", title_size, 430, "featured title")
    ensure_fits("AI CODING AGENT FOR THE TERMINAL", "mono", 9.2, 430, "featured category")
    ensure_fits(project["platforms"], "mono", 8.2, 430, "featured platforms")
    ensure_fits(project["tech"], "mono", 7.8, 430, "featured tech")
    ensure_fits(web + " ↗", "mono", 8.8, 420, "featured website")
    ensure_fits(repo + " ↗", "mono", 7.8, 300, "featured repository")
    label = (f'{project["name"]} {project["version"]} - flagship AI coding agent for the terminal on Windows, Linux and macOS. '
             f'Reads the project, edits real files, runs commands and verifies results. '
             f'Official website {project["live"]} and GitHub repository {project["repo"]}.')
    return svg_doc(W, H, "".join(body), label, fonts=("serif", "sans", "mono"), pad_bottom=14)


def render_project(project, delay):
    H = 180
    cw = W / 2 - 10
    inner = cw - 48
    size, lines = fit_lines(project["desc"], "sans", 11.6, 382, 2)
    body = [
        f'<text class="f"{d(delay)} x="24" y="32" {ff("mono", 8.8, MUTED)} letter-spacing="1.2">{project["index"]}</text>',
        f'<text class="f"{d(delay + 0.04)} x="{cw - 24}" y="32" {ff("mono", 8.0, MUTED)} text-anchor="end" letter-spacing="1.1">{project["category"]}</text>',
        f'<text class="r"{d(delay + 0.06)} x="24" y="76" {ff("serif", 24, INK)} letter-spacing="-0.4">{esc(project["name"])}</text>',
        f'<g class="f"{d(delay + 0.12)}><rect x="{cw - 56}" y="46" width="32" height="32" rx="8" fill="none" stroke="{RULE_HI}"/>',
        K.project_icon(cw - 54, 48, project["slug"], SOFT),
        '</g>',
        f'<line class="f"{d(delay + 0.16)} x1="24" y1="134" x2="{cw - 24}" y2="134" stroke="{RULE}"/>',
        f'<text class="f"{d(delay + 0.2)} x="24" y="157" {ff("mono", 7.9, MUTED)} letter-spacing=".55">{esc(project["tags"])}</text>',
        f'<text class="f"{d(delay + 0.24)} x="{cw - 24}" y="157" {ff("mono", 8.0, SOFT)} text-anchor="end" letter-spacing=".6">LIVE ↗</text>',
    ]
    for i, line in enumerate(lines):
        body.append(f'<text class="f"{d(delay + 0.10 + i * 0.04)} x="24" y="{99 + i * 16}" {ff("sans", size, SOFT)}>{esc(line)}</text>')
    ensure_fits(project["name"], "serif", 24, inner - 46, "project name")
    ensure_fits(project["tags"], "mono", 7.9, inner - 60, "project tags")
    label = f'{project["name"]} - {project["desc"]} {project["live"]}'
    return svg_doc(cw, H, "".join(body), label,
                   fonts=("serif", "sans", "mono"), pad_left=5, pad_right=5, pad_bottom=14)


# ---- skills ----------------------------------------------------------------
def render_skills(data):
    H = 358
    cols = len(C.SKILLS)
    col_w = 146
    start = PAD
    step = 160
    total_items = sum(len(items) for _, _, items in C.SKILLS)
    head_html = head("05", "TOOLKIT", "What I ", "build with", data=data,
                     right=f"{total_items} TOOLS & TECHNOLOGIES")
    body = [head_html]
    # tallest column determines the card height; keep a fixed, generous slot
    for i, (index, title, items) in enumerate(C.SKILLS):
        x = start + i * step
        body.append(f'<text class="f"{d(0.14 + i * 0.05)} x="{x}" y="134" {ff("mono", 7.8, FAINT)} letter-spacing="1.1">{index}</text>')
        title_lines = K.wrap_px(title, "sans-6", 11.5, col_w)
        for j, line in enumerate(title_lines[:2]):
            body.append(f'<text class="r"{d(0.16 + i * 0.05 + j * 0.03)} x="{x}" y="{154 + j * 14}" {ff("sans-6", 11.5, INK)}>{esc(line)}</text>')
        body.append(f'<line class="f"{d(0.2 + i * 0.05)} x1="{x}" y1="178" x2="{x + col_w}" y2="178" stroke="{RULE}"/>')
        y = 198
        for item in items:
            item_lines = K.wrap_px(item, "sans", 11.1, col_w - 9)
            if y == 198:
                pass
            for k, line in enumerate(item_lines):
                if k == 0:
                    body.append(f'<line class="f"{d(0.22 + i * 0.05)} x1="{x}" y1="{y - 4}" x2="{x + 3.5}" y2="{y - 4}" stroke="{ACCENT}" stroke-opacity=".7"/>')
                body.append(f'<text class="f"{d(0.24 + i * 0.05)} x="{x + 9}" y="{y}" {ff("sans", 11.1, SOFT)}>{esc(line)}</text>')
                y += 16.4
            y += 0.6
        if i:
            body.append(vrule(x - 14, 122, 336, RULE))
    label = ("Toolkit: Python, JavaScript, FastAPI, REST and Gmail APIs, Supabase Auth and row-level security, "
             "OpenRouter, Ollama, Git, Vercel, Cloudflare and Linux.")
    return svg_doc(W, H, "".join(body), label, fonts=ALL_FONTS)


# ---- experience ------------------------------------------------------------
def render_experience(data):
    head_html = head("06", "EXPERIENCE", "Where I've ", "worked", data=data,
                     right=f"{len(C.EXPERIENCE):02d} ROLES")
    rows = []
    for entry in C.EXPERIENCE:
        bullet_lines = [K.wrap_px(b, "sans", 11.7, 636) for b in entry["bullets"]]
        rows.append((entry, bullet_lines))

    y = 148
    body = [head_html]
    nodes = []
    for r, (entry, bullet_lines) in enumerate(rows):
        delay = 0.18 + r * 0.12
        nodes.append(y - 5)
        body.append(f'<circle class="p"{d(delay)} cx="52" cy="{y - 5}" r="4.5" fill="{CARD}" stroke="{RULE_HI}"/>')
        body.append(f'<circle class="p"{d(delay + 0.02)} cx="52" cy="{y - 5}" r="1.6" fill="{ACCENT}"/>')
        role_size = 15.5
        ensure_fits(entry["role"], "sans-6", role_size, 620, "experience role")
        body.append(f'<text class="r"{d(delay)} x="76" y="{y}" {ff("sans-6", role_size, INK)}>{esc(entry["role"])}</text>')
        body.append(f'<text class="f"{d(delay + 0.04)} x="{RIGHT}" y="{y}" {ff("mono", 8.3, MUTED)} text-anchor="end" letter-spacing=".8">{esc(entry["meta"])}</text>')
        org_w = measure(entry["org"], "sans", 12)
        body.append(f'<text class="f"{d(delay + 0.06)} x="76" y="{y + 20}" {ff("sans", 12, ACCENT)}>{esc(entry["org"])}</text>')
        body.append(f'<text class="f"{d(delay + 0.06)} x="{76 + org_w + 10:.1f}" y="{y + 20}" {ff("mono", 8.0, MUTED)}>{esc(entry["place"])}</text>')
        by = y + 43
        for lines in bullet_lines:
            for k, line in enumerate(lines):
                body.append(f'<text class="f"{d(delay + 0.08)} x="{88 if k == 0 else 96}" y="{by}" {ff("sans", 11.7, SOFT)}>{esc(line)}</text>')
                if k == 0:
                    body.append(f'<line x1="76" y1="{by - 4}" x2="80" y2="{by - 4}" stroke="{ACCENT}" stroke-opacity=".6"/>')
                by += 18
        y = by + 26

    line_end = nodes[-1] + 12 if nodes else 460
    body.insert(1, f'<line class="f" x1="52" y1="126" x2="52" y2="{line_end}" stroke="{RULE}"/>')
    H = max(470, int(y + 6))
    label = ("Experience: founder and independent developer at EAGOX Studio; freelance web and AI voice work; "
             "junior system deployment engineer for City Bank PLC via TriTech Computers, May to October 2026.")
    return svg_doc(W, H, "".join(body), label, fonts=ALL_FONTS)


# ---- education -------------------------------------------------------------
def render_education(data):
    H = 238
    head_html = head("07", "EDUCATION", "The ", "foundation", data=data,
                     right="DHAKA · MYMENSINGH")
    body = [head_html]
    for i, item in enumerate(C.EDUCATION):
        x = PAD + i * 430
        width = 360
        body.append(f'<text class="f"{d(0.14 + i * 0.08)} x="{x}" y="134" {ff("mono", 7.8, FAINT)} letter-spacing="1.1">{i + 1:02d}</text>')
        body.append(f'<line class="f"{d(0.16 + i * 0.08)} x1="{x}" y1="122" x2="{x + width}" y2="122" stroke="{RULE}"/>')
        body.append(f'<text class="r"{d(0.18 + i * 0.08)} x="{x}" y="148" {ff("sans-6", 14, INK)}>{esc(item["degree"])}</text>')
        body.append(f'<text class="f"{d(0.22 + i * 0.08)} x="{x}" y="168" {ff("sans", 11.5, SOFT)}>{esc(item["field"])}</text>')
        body.append(f'<text class="f"{d(0.26 + i * 0.08)} x="{x}" y="188" {ff("sans", 11.5, MUTED)}>{esc(item["school"])}</text>')
        body.append(f'<text class="f"{d(0.3 + i * 0.08)} x="{x}" y="210" {ff("mono", 8.3, ACCENT)} letter-spacing=".7">{esc(item["meta"])}</text>')
        body.append(f'<text class="f"{d(0.34 + i * 0.08)} x="{x + width}" y="210" {ff("mono", 8.2, MUTED)} text-anchor="end">{esc(item["note"])}</text>')
    body.append(vrule(452, 122, 214, RULE))
    label = ("Education: Diploma in Engineering, Computer Science and Technology, Dhaka Polytechnic Institute, "
             "September 2025 to present; SSC, Hashil Higher Secondary School, 2025, GPA 4.72 out of 5.")
    return svg_doc(W, H, "".join(body), label, fonts=ALL_FONTS)


# ---- orchestration ---------------------------------------------------------
def load_data(path):
    if not os.path.exists(path):
        raise SystemExit(f"missing {path}; run python scripts/fetch_contributions.py first")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    for key in ("username", "range", "total_contributions", "active_days", "current_streak",
                "longest_streak", "best_day", "current_month", "monthly", "days"):
        if key not in data:
            raise SystemExit(f"{path} is missing required key '{key}'")
    if len(data["days"]) < 30:
        raise SystemExit(f"{path} has too few days to render a year")
    return data


def write(out_dir, rel_path, text):
    path = os.path.join(out_dir, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"  {rel_path:38s} {len(text) / 1024:6.1f} KB")


def update_readme_stamp(readme_path, data):
    if not os.path.exists(readme_path):
        return
    with open(readme_path, encoding="utf-8") as fh:
        text = fh.read()
    stamp = f'<!-- refreshed: {data["generated_at"][:10]} | {data["source"]} -->'
    updated = re.sub(r"<!-- refreshed:.*?-->", stamp, text, count=1)
    if updated != text:
        with open(readme_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(updated)
        print(f"  updated refresh stamp in {os.path.basename(readme_path)}")


def generate(out_dir, data, ascii_rows, stamp=False):
    print(f"rendering {'STATIC' if not K.MOTION else 'animated'} cards -> {out_dir}")
    print(f"  portrait: {len(ascii_rows)} rows x {len(ascii_rows[0])} characters")
    write(out_dir, "hero.svg", render_hero(data, ascii_rows))
    for i, tile in enumerate(C.TILES):
        write(out_dir, f'{tile["slug"]}.svg', render_tile(tile, 1.22 + i * 0.08))
    write(out_dir, "about.svg", render_about(data))
    write(out_dir, "monthly-activity.svg", render_activity(data))
    write(out_dir, "contribution-graph.svg", render_heatmap(data))
    write(out_dir, "title-work.svg", render_work_title())
    featured = C.PROJECTS[0]
    if not featured.get("flagship"):
        raise AssertionError("the first project must be the SeedCode CLI flagship")
    write(out_dir, f'projects/{featured["slug"]}.svg', render_featured(featured))
    write(out_dir, "rail-products.svg", render_subsection("MORE PRODUCTS", "04 BUILDS"))
    for i, project in enumerate(C.PROJECTS[1:]):
        write(out_dir, f'projects/{project["slug"]}.svg', render_project(project, 2.95 + i * 0.1))
    write(out_dir, "rail-experiments.svg", render_subsection("EXPERIMENTS & TOOLS", "01 SIDE BUILD"))
    write(out_dir, "skills.svg", render_skills(data))
    write(out_dir, "experience.svg", render_experience(data))
    write(out_dir, "education.svg", render_education(data))
    if stamp:
        update_readme_stamp(os.path.join(HERE, "README.md"), data)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render the profile cards")
    parser.add_argument("--out", default=os.environ.get("PROFILE_OUT", os.path.join(HERE, "cards")))
    parser.add_argument("--data", default=os.environ.get("PROFILE_DATA", os.path.join(HERE, "data", "contributions.json")))
    parser.add_argument("--static", action="store_true", help="disable all animation (same as STATIC=1)")
    parser.add_argument("--no-check", action="store_true")
    parser.add_argument("--stamp", action="store_true", help="update the README refresh comment")
    args = parser.parse_args(argv)

    if args.static:
        K.MOTION = False
    out_dir = os.path.abspath(args.out)
    data = load_data(os.path.abspath(args.data))

    if data.get("sample") and out_dir == os.path.abspath(os.path.join(HERE, "cards")):
        raise SystemExit("refusing to render a SAMPLE fixture into cards/. Use --out for tests.")

    ascii_rows = A.load_rows()
    generate(out_dir, data, ascii_rows, stamp=args.stamp or out_dir == os.path.abspath(os.path.join(HERE, "cards")))

    if not args.no_check:
        import validate_output
        ok = validate_output.validate_dir(
            out_dir, data,
            readme=os.path.join(HERE, "README.md"),
            static=not K.MOTION,
            quiet=False,
        )
        if not ok:
            return 1
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
