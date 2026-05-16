#!/usr/bin/env python3
"""Download Friday Rock Show MP3 episodes from Mixcloud via yt-dlp.

Scrapes the episode checklist at dawtrina.com to find Mixcloud URLs for the
requested year/month, then downloads each one with yt-dlp, saving files as
FRS YYYY-MM-DD.mp3.

Examples:
  python scripts/download_episodes.py 1980
  python scripts/download_episodes.py 1981 --month 03
  python scripts/download_episodes.py 1980 --month 01 --dry-run

Output directory: /media/andy/DATA/Projects/The Friday Rock Show Registry/FRSAudio/Source/<year>/

Requirements:
  - yt-dlp available on PATH (sudo apt install yt-dlp  or  pip install yt-dlp)
  - requests, beautifulsoup4  (pip install requests beautifulsoup4 lxml)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


CHECKLIST_URL = "https://www.dawtrina.com/music/frs/checklist.html"
OUTPUT_BASE = Path(
    "/media/andy/DATA/Projects/The Friday Rock Show Registry/FRSAudio/Source"
)
YEAR_MIN = 1978
YEAR_MAX = 1993


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(tag: str, msg: str) -> None:
    """Print a tagged diagnostic line immediately (unbuffered)."""
    print(f"[{tag}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_date(day_mon: str, year: int) -> str | None:
    """Convert '4 Jan' + 1980 → '1980-01-04'.  Returns None on any parse failure."""
    try:
        dt = datetime.strptime(f"{day_mon.strip()} {year}", "%d %b %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def fetch_episodes(year: int) -> list[tuple[str, str]]:
    """Fetch the checklist and return (iso_date, mixcloud_url) pairs for *year*.

    Episodes with no Mixcloud link are silently omitted from the results.
    """
    log("FETCH", f"Requesting {CHECKLIST_URL}")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; FRS-downloader/1.0)"}
    try:
        r = requests.get(CHECKLIST_URL, headers=headers, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error: {exc}") from exc

    log("FETCH OK", f"HTTP {r.status_code} — {len(r.content):,} bytes received")
    r.raise_for_status()

    log("PARSE", "Parsing HTML with BeautifulSoup …")
    soup = BeautifulSoup(r.text, "lxml")
    tables = soup.find_all("table")
    log("PARSE", f"Found {len(tables)} HTML table(s) on the page")

    # The main episode data table is the largest one
    main_table = max(tables, key=lambda t: len(t.find_all("tr")))
    all_rows = main_table.find_all("tr")
    log("PARSE", f"Main data table has {len(all_rows)} row(s) — scanning for year {year} …")

    in_year = False
    episodes: list[tuple[str, str]] = []
    total_rows_for_year = 0
    no_mixcloud_count = 0
    parse_errors = 0

    for row in all_rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        texts = [c.get_text(strip=True) for c in cells]

        # ── Year-marker row: a single cell whose text is exactly the year ────
        if len(texts) == 1 and texts[0] == str(year):
            log("PARSE", f"Found year section marker: {year}")
            in_year = True
            continue

        # ── Leaving this year's section: next single-cell year marker ────────
        if (
            in_year
            and len(texts) == 1
            and texts[0].isdigit()
            and int(texts[0]) != year
        ):
            log("PARSE", f"Reached end of year {year} section (next year: {texts[0]})")
            break

        if not in_year:
            continue

        # ── Header row ────────────────────────────────────────────────────────
        if texts[0] == "#":
            continue

        # ── Skip note-only rows (no episode number or too few cells) ─────────
        if not texts[0].strip() or len(texts) < 4:
            continue

        total_rows_for_year += 1
        date_raw = texts[1].strip()

        iso_date = parse_date(date_raw, year)
        if iso_date is None:
            log("PARSE", f"  WARNING: could not parse date '{date_raw}' — skipping row")
            parse_errors += 1
            continue

        # ── Look for a Mixcloud link (href contains mixcloud.com) ─────────────
        # Some rows also have YouTube links; we want only the Mixcloud one.
        # The anchor text is "Mixcloud" for the Mixcloud link.
        mixcloud_url: str | None = None
        for a_tag in row.find_all("a"):
            href = a_tag.get("href", "")
            if "mixcloud.com" in href and a_tag.get_text(strip=True) == "Mixcloud":
                mixcloud_url = href
                break

        if mixcloud_url is None:
            no_mixcloud_count += 1
            continue

        episodes.append((iso_date, mixcloud_url))

    log(
        "PARSE",
        (
            f"Year {year} totals: {total_rows_for_year} episode row(s) found, "
            f"{len(episodes)} have a Mixcloud link, "
            f"{no_mixcloud_count} have no Mixcloud link (skipped), "
            f"{parse_errors} date parse error(s)"
        ),
    )
    return episodes


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_episode(
    iso_date: str,
    mixcloud_url: str,
    out_path: Path,
    cookies_browser: str | None,
) -> bool:
    """Run yt-dlp to download *mixcloud_url* as MP3 to *out_path*.

    Returns True on success, False on failure.
    Raises FileNotFoundError if yt-dlp is not on PATH.
    """
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--no-playlist",
        "-o", str(out_path),
    ]
    if cookies_browser:
        cmd += ["--cookies-from-browser", cookies_browser]
    cmd.append(mixcloud_url)

    log("CMD", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        size_mb = out_path.stat().st_size / (1024 * 1024) if out_path.exists() else 0.0
        log("OK", f"Saved → {out_path}  ({size_mb:.1f} MB)")
        return True

    # ── Failure: show the last few lines of yt-dlp stderr ────────────────────
    stderr_lines = result.stderr.strip().splitlines() if result.stderr.strip() else []
    tail = stderr_lines[-5:] if len(stderr_lines) > 5 else stderr_lines
    log("FAIL", f"{iso_date}  {mixcloud_url}  (yt-dlp exit {result.returncode})")
    for line in tail:
        log("FAIL", f"  yt-dlp: {line}")
    return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download Friday Rock Show MP3s from Mixcloud.",
        epilog=(
            "Examples:\n"
            "  %(prog)s 1980\n"
            "  %(prog)s 1981 --month 03\n"
            "  %(prog)s 1980 --month 01 --dry-run\n\n"
            "If Mixcloud requires authentication, supply --cookies-browser chrome\n"
            "(or firefox, edge, etc.) to read saved login cookies automatically."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "year",
        type=int,
        metavar="YEAR",
        help=f"4-digit broadcast year ({YEAR_MIN}–{YEAR_MAX})",
    )
    parser.add_argument(
        "--month",
        metavar="MM",
        help="2-digit month (01–12); omit to download all episodes for the year",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be downloaded without actually downloading anything",
    )
    parser.add_argument(
        "--cookies-browser",
        metavar="BROWSER",
        help="Pass saved login cookies from BROWSER to yt-dlp (e.g. chrome, firefox)",
    )
    args = parser.parse_args()

    # ── Validate year ─────────────────────────────────────────────────────────
    if not YEAR_MIN <= args.year <= YEAR_MAX:
        parser.error(f"year must be between {YEAR_MIN} and {YEAR_MAX}")

    # ── Validate month ────────────────────────────────────────────────────────
    month_filter: int | None = None
    month_label = "all months"
    if args.month:
        if not (args.month.isdigit() and 1 <= int(args.month) <= 12):
            parser.error("--month must be a two-digit value between 01 and 12")
        month_filter = int(args.month)
        month_label = f"month {args.month}"

    out_dir = OUTPUT_BASE / str(args.year)

    log("START", "=" * 60)
    log("START", f"Friday Rock Show episode downloader")
    log("START", f"  Year   : {args.year}")
    log("START", f"  Months : {month_label}")
    log("START", f"  Output : {out_dir}")
    log("START", f"  Dry run: {args.dry_run}")
    if args.cookies_browser:
        log("START", f"  Cookies: from browser '{args.cookies_browser}'")
    log("START", "=" * 60)

    # ── Fetch and parse the checklist ─────────────────────────────────────────
    try:
        episodes = fetch_episodes(args.year)
    except Exception as exc:
        log("FAIL", f"Could not retrieve episode list: {exc}")
        return 1

    if not episodes:
        log("DONE", f"No episodes with Mixcloud links found for year {args.year}.")
        return 0

    # ── Apply month filter ────────────────────────────────────────────────────
    if month_filter is not None:
        before = len(episodes)
        episodes = [
            (d, u)
            for d, u in episodes
            if datetime.fromisoformat(d).month == month_filter
        ]
        log(
            "PARSE",
            f"Month filter ({args.month}): {before} episode(s) → {len(episodes)} after filtering",
        )

    if not episodes:
        log("DONE", f"No episodes found for year={args.year} month={args.month}.")
        return 0

    log("START", f"{len(episodes)} episode(s) to process")

    # ── Create output directory ───────────────────────────────────────────────
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        log("START", f"Output directory ready: {out_dir}")

    # ── Download loop ─────────────────────────────────────────────────────────
    total = len(episodes)
    downloaded = 0
    skipped = 0
    failed = 0

    for idx, (iso_date, mixcloud_url) in enumerate(episodes, start=1):
        filename = f"FRS {iso_date}.mp3"
        out_path = out_dir / filename

        log(f"DOWNLOAD {idx}/{total}", f"Date: {iso_date}")
        log(f"DOWNLOAD {idx}/{total}", f"URL : {mixcloud_url}")
        log(f"DOWNLOAD {idx}/{total}", f"File: {out_path}")

        # ── Skip if already downloaded ────────────────────────────────────────
        if out_path.exists():
            size_mb = out_path.stat().st_size / (1024 * 1024)
            log("SKIP", f"Already exists ({size_mb:.1f} MB) — {out_path}")
            skipped += 1
            continue

        # ── Dry run ───────────────────────────────────────────────────────────
        if args.dry_run:
            log("OK", f"[DRY-RUN] Would download → {out_path}")
            downloaded += 1
            continue

        # ── Actual download ───────────────────────────────────────────────────
        try:
            success = download_episode(iso_date, mixcloud_url, out_path, args.cookies_browser)
        except FileNotFoundError:
            log("FAIL", "yt-dlp executable not found on PATH.")
            log("FAIL", "  Install with:  sudo apt install yt-dlp")
            log("FAIL", "            or:  pip install yt-dlp")
            return 1
        except Exception as exc:
            log("FAIL", f"{iso_date}: unexpected error: {exc}")
            failed += 1
            continue

        if success:
            downloaded += 1
        else:
            failed += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    log("DONE", "=" * 60)
    log("DONE", f"Run complete for year={args.year}  months={month_label}")
    log("DONE", f"  Downloaded : {downloaded}")
    log("DONE", f"  Skipped    : {skipped}  (already on disk)")
    log("DONE", f"  Failed     : {failed}")
    log("DONE", f"  Total      : {total}")
    log("DONE", "=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
