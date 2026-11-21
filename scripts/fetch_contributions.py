#!/usr/bin/env python3
"""
Collect real GitHub contribution data and write data/contributions.json.

Order of preference:
  1. GitHub GraphQL API with GITHUB_TOKEN (supported, documented).
  2. GitHub's public contribution calendar HTML (no token, best effort).
  3. Keep the existing JSON untouched and exit successfully so a daily run never
     replaces good data with an error page.

There is also an explicit `--sample` mode for rendering tests. Sample data is
marked `"sample": true`, gets a visible "SAMPLE DATA" banner on the cards, and is
never written to data/contributions.json.

Usage:
    python scripts/fetch_contributions.py
    python scripts/fetch_contributions.py --check
    python scripts/fetch_contributions.py --sample /tmp/sample.json

Environment:
    GITHUB_TOKEN   optional; a classic PAT with `read:user` or a fine-grained
                   token with public profile read access. The Actions token works
                   for public contributions.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA_PATH = os.path.join(ROOT, "data", "contributions.json")
USER = "Alshahriar-07"
API_URL = "https://api.github.com/graphql"
HTML_URL = "https://github.com/users/{user}/contributions"
UA = "Alshahriar-07-profile-readme/1.0 (+https://github.com/Alshahriar-07)"

LEVELS = ((20, 5), (10, 4), (6, 3), (3, 2), (1, 1), (0, 0))


def level_for(count: int) -> int:
    for threshold, level in LEVELS:
        if count >= threshold:
            return level
    return 0


# ---- collection ------------------------------------------------------------
def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/vnd.github+json"})
    return s


def _retry_get(session, url, **kwargs):
    last = None
    for attempt in range(3):
        try:
            resp = session.get(url, timeout=30, **kwargs)
            if resp.status_code in (403, 429) and attempt < 2:
                wait = int(resp.headers.get("Retry-After", 0)) or (4 * (attempt + 1))
                print(f"  rate limited ({resp.status_code}); retrying in {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"request failed: {last}")


def fetch_graphql(user: str, token: str) -> list[dict]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    query = """
    query ProfileContributions($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays { date contributionCount }
            }
          }
        }
      }
    }
    """
    variables = {
        "login": user,
        "from": f"{start.isoformat()}T00:00:00Z",
        "to": f"{today.isoformat()}T23:59:59Z",
    }
    session = _session()
    session.headers["Authorization"] = f"bearer {token}"
    resp = session.post(API_URL, json={"query": query, "variables": variables}, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"GraphQL HTTP {resp.status_code}")
    payload = resp.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0].get("message", "GraphQL error"))
    user_data = payload.get("data", {}).get("user")
    if not user_data:
        raise RuntimeError("GraphQL returned no user")
    calendar_data = user_data["contributionsCollection"]["contributionCalendar"]
    if calendar_data.get("totalContributions", 0) <= 0:
        raise RuntimeError("GraphQL calendar is empty")
    days = []
    for week in calendar_data["weeks"]:
        for day in week["contributionDays"]:
            days.append({"date": day["date"], "count": int(day["contributionCount"])})
    return _clean_days(days)


def fetch_html(user: str) -> list[dict]:
    session = _session()
    session.headers["Accept"] = "text/html,application/xhtml+xml"
    resp = _retry_get(session, HTML_URL.format(user=user))
    soup = BeautifulSoup(resp.text, "html.parser")
    cells = soup.select("td.ContributionCalendar-day")
    if not cells:
        raise RuntimeError("contribution calendar not present in HTML")

    tooltips = {}
    for tip in soup.find_all("tool-tip"):
        target = tip.get("for")
        if target:
            tooltips[target] = tip.get_text(" ", strip=True)

    days = []
    unparsed = 0
    for cell in cells:
        iso = cell.get("data-date")
        if not iso:
            continue
        text = tooltips.get(cell.get("id", ""), "") or cell.get("aria-label", "")
        if re.search(r"no contributions?", text, re.I):
            count = 0
        else:
            match = re.search(r"([\d,]+)\s+contributions?", text, re.I)
            if not match:
                # A non-zero level with an unparseable tooltip must not be
                # silently recorded as zero. Count it, then fail rather than
                # publish an undercount.
                if cell.get("data-level") not in (None, "0"):
                    unparsed += 1
                    continue
                count = 0
            else:
                count = int(match.group(1).replace(",", ""))
        days.append({"date": iso, "count": count})
    if unparsed > 5:
        raise RuntimeError(f"{unparsed} contribution cells had no parseable count")
    cleaned = _clean_days(days)
    if sum(day["count"] for day in cleaned) == 0:
        raise RuntimeError("calendar contains no contribution counts")
    return cleaned


def _clean_days(days: list[dict]) -> list[dict]:
    by_date = {}
    for item in days:
        iso = item["date"]
        date.fromisoformat(iso)  # raises on malformed dates
        by_date[iso] = max(0, int(item["count"]))
    ordered = sorted(by_date.items())
    if len(ordered) < 30:
        raise RuntimeError(f"only {len(ordered)} contribution days parsed")

    # The calendar is a contiguous range. If a cell is missing, treat it as a
    # zero day rather than shifting every later date.
    filled = []
    cursor = date.fromisoformat(ordered[0][0])
    end = date.fromisoformat(ordered[-1][0])
    lookup = dict(ordered)
    gaps = 0
    while cursor <= end:
        iso = cursor.isoformat()
        if iso not in lookup:
            gaps += 1
            filled.append({"date": iso, "count": 0})
        else:
            filled.append({"date": iso, "count": lookup[iso]})
        cursor += timedelta(days=1)
    if gaps:
        print(f"  note: filled {gaps} missing calendar day(s) with 0", file=sys.stderr)
    return filled


# ---- statistics ------------------------------------------------------------
def build_stats(days: list[dict], source: str, sample: bool = False) -> dict:
    parsed = [(date.fromisoformat(d["date"]), int(d["count"])) for d in days]
    parsed.sort()
    if not parsed:
        raise ValueError("no contribution days")

    counts = [c for _, c in parsed]
    total = sum(counts)
    active = sum(1 for c in counts if c > 0)

    longest = current_run = 0
    longest_range = None
    run_start = None
    for i, (day, count) in enumerate(parsed):
        if count > 0:
            if current_run == 0:
                run_start = day
            current_run += 1
            if current_run > longest:
                longest = current_run
                longest_range = (run_start, day)
        else:
            current_run = 0

    last_day, last_count = parsed[-1]
    idx = len(parsed) - 1
    if last_count == 0 and last_day == date.today():
        idx -= 1  # today is still in progress
    current = 0
    while idx >= 0 and parsed[idx][1] > 0:
        current += 1
        idx -= 1

    best_day, best_count = max(parsed, key=lambda pair: (pair[1], pair[0]))

    monthly = []
    month_map: dict[str, dict] = {}
    for day, count in parsed:
        key = day.strftime("%Y-%m")
        bucket = month_map.setdefault(
            key,
            {"month": key, "label": calendar.month_abbr[day.month].upper(), "total": 0, "active_days": 0},
        )
        bucket["total"] += count
        bucket["active_days"] += 1 if count else 0
    for key in sorted(month_map):
        bucket = month_map[key]
        bucket["days_in_month"] = calendar.monthrange(int(key[:4]), int(key[5:7]))[1]
        best = max((pair for pair in parsed if pair[0].strftime("%Y-%m") == key), key=lambda p: p[1])
        bucket["best_day"] = {"date": best[0].isoformat(), "count": best[1]}
        monthly.append(bucket)

    current_month = monthly[-1]
    previous = monthly[-2] if len(monthly) > 1 else None

    # A partial month must not be compared with a full previous month. Compare
    # the same number of elapsed days (e.g. Nov 1-21 vs Oct 1-21).
    trend = None
    trend_basis = None
    trend_prev_total = None
    if previous:
        month_end = calendar.monthrange(last_day.year, last_day.month)[1]
        partial = last_day.day < month_end
        cutoff = last_day.day if partial else 31
        trend_prev_total = sum(
            count for day, count in parsed
            if day.strftime("%Y-%m") == previous["month"] and day.day <= cutoff
        )
        if trend_prev_total > 0:
            trend = round((current_month["total"] - trend_prev_total) / trend_prev_total * 100)
        trend_basis = f"{previous['label']} 1-{cutoff}" if partial else previous["label"]

    source_label = {
        "github-graphql": "GitHub GraphQL API",
        "github-html": "GitHub public contribution calendar",
        "sample": "Sample fixture (not real data)",
    }.get(source, source)

    result = {
        "schema_version": 1,
        "username": USER,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": source,
        "source_label": source_label,
        "sample": sample,
        "range": {"from": parsed[0][0].isoformat(), "to": parsed[-1][0].isoformat()},
        "total_contributions": total,
        "active_days": active,
        "tracked_days": len(parsed),
        "avg_per_active_day": round(total / active, 2) if active else 0,
        "current_streak": current,
        "longest_streak": longest,
        "longest_streak_range": (
            {"from": longest_range[0].isoformat(), "to": longest_range[1].isoformat()} if longest_range else None
        ),
        "last_active": next((day.isoformat() for day, c in reversed(parsed) if c > 0), None),
        "best_day": {"date": best_day.isoformat(), "count": best_count},
        "current_month": {
            "month": current_month["month"],
            "label": current_month["label"],
            "total": current_month["total"],
            "active_days": current_month["active_days"],
            "best_day": current_month["best_day"],
            "previous_month": previous["month"] if previous else None,
            "previous_total": previous["total"] if previous else None,
            "trend_previous_total": trend_prev_total,
            "trend_basis": trend_basis,
            "partial": last_day.day < calendar.monthrange(last_day.year, last_day.month)[1],
            "trend_pct": trend,
        },
        "monthly": monthly,
        "days": [{"date": day.isoformat(), "count": count, "level": level_for(count)} for day, count in parsed],
    }
    if sample:
        result["note"] = (
            "SAMPLE FIXTURE - generated by --sample for rendering tests only. "
            "This is not real contribution data and must never be presented as such."
        )
    return result


# ---- sample fixture --------------------------------------------------------
def sample_days(days: int = 371, end: date | None = None) -> list[dict]:
    end = end or date.today()
    start = end - timedelta(days=days - 1)
    out = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        digest = hashlib.sha256(f"sample-{day.isoformat()}".encode()).digest()
        base = digest[0]
        weekday = day.weekday()
        if weekday in (5, 6) and base % 3:
            count = 0
        elif base < 70:
            count = 0
        elif base < 130:
            count = 1 + digest[1] % 3
        elif base < 190:
            count = 4 + digest[1] % 4
        else:
            count = 8 + digest[1] % 9
        out.append({"date": day.isoformat(), "count": count})
    return out


# ---- output ----------------------------------------------------------------
def _atomic_json(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def load_json(path: str = DATA_PATH) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if data.get("days") else None
    except (OSError, ValueError):
        return None


def load_existing(path: str = DATA_PATH) -> dict | None:
    """Previous real data only; a sample fixture is never reused as a fallback."""
    data = load_json(path)
    return data if data and not data.get("sample") else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Refresh contribution data for the profile cards")
    parser.add_argument("--out", default=DATA_PATH, help="output JSON path")
    parser.add_argument("--user", default=USER, help="GitHub login")
    parser.add_argument("--sample", nargs="?", const=os.path.join(ROOT, "data", "sample-contributions.json"),
                        help="write an explicitly labeled sample fixture instead of fetching")
    parser.add_argument("--check", action="store_true", help="print a summary of the existing JSON and exit")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if args.check:
        data = load_json(args.out)
        if not data:
            print(f"no valid contribution data at {args.out}", file=sys.stderr)
            return 1
        label = " [SAMPLE FIXTURE - NOT REAL DATA]" if data.get("sample") else ""
        print(f"{data['username']}: {data['total_contributions']} contributions, "
              f"{data['active_days']} active days, {data['current_streak']}d current / "
              f"{data['longest_streak']}d longest streak ({data['source']}){label}")
        return 0

    if args.sample:
        stats = build_stats(sample_days(), "sample", sample=True)
        _atomic_json(args.sample, stats)
        print(f"wrote labeled SAMPLE fixture to {os.path.relpath(args.sample, ROOT)} "
              f"({stats['total_contributions']} sample contributions). Not real data.")
        return 0

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    days = None
    source = None
    if token:
        try:
            days = fetch_graphql(args.user, token)
            source = "github-graphql"
            print(f"fetched {len(days)} days via GitHub GraphQL")
        except Exception as exc:  # noqa: BLE001 - fall through to the public calendar
            print(f"GraphQL unavailable ({exc}); trying public contribution calendar", file=sys.stderr)
    if days is None:
        try:
            days = fetch_html(args.user)
            source = "github-html"
            print(f"fetched {len(days)} days via public contribution calendar")
        except Exception as exc:  # noqa: BLE001 - keep the previous data
            print(f"contribution fetch failed: {exc}", file=sys.stderr)
            existing = load_existing(args.out)
            if existing:
                print("keeping existing contribution data; no changes written")
                return 0
            return 1

    previous = load_existing(args.out)
    stats = build_stats(days, source)
    if previous and previous.get("total_contributions", 0) > 0 and stats["total_contributions"] == 0:
        print("refusing to replace non-zero data with an empty calendar", file=sys.stderr)
        return 1

    # A refresh that only changes generated_at is not worth a commit.
    if previous:
        old = {key: value for key, value in previous.items() if key != "generated_at"}
        new = {key: value for key, value in stats.items() if key != "generated_at"}
        if old == new:
            print("contribution data unchanged; nothing written")
            return 0

    _atomic_json(args.out, stats)
    if not args.quiet:
        print(
            f"wrote {os.path.relpath(args.out, ROOT)}: {stats['total_contributions']} contributions, "
            f"{stats['active_days']} active days, current streak {stats['current_streak']}, "
            f"longest {stats['longest_streak']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
