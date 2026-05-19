#!/usr/bin/env python3
"""Download Friday Rock Show MP3 episodes from Mixcloud via yt-dlp,
or from the Fandom wiki (Mega/Mediafire/YouTube/Mixcloud) via --fandom.

Examples:
  python scripts/download_episodes.py --year 1980
  python scripts/download_episodes.py --year 1981 --month 03
  python scripts/download_episodes.py --year 1980 --month 01 --dry-run
  python scripts/download_episodes.py --year 1987 --fandom --dry-run
  python scripts/download_episodes.py --year 1987 --fandom --month 01
  python scripts/download_episodes.py --year 1986 1987 1988 --fandom

Output directory: /media/andy/DATA/Projects/The Friday Rock Show Registry/FRSAudio/Source/<year>/
Log file (fandom path): <output_dir>/download-fandom-<year>.log

Requirements:
  - yt-dlp available on PATH (sudo apt install yt-dlp  or  pip install yt-dlp)
  - requests, beautifulsoup4, lxml  (pip install requests beautifulsoup4 lxml)
  - curl_cffi  (pip install curl-cffi)   [--fandom path only]
  - cookies.txt (Netscape format) at repo root  [--fandom path only]
"""
from __future__ import annotations

import argparse
import http.cookiejar
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import TextIO

import requests
from bs4 import BeautifulSoup, Tag

try:
    from curl_cffi import requests as cffi_requests
    _CFFI_AVAILABLE = True
except ImportError:
    _CFFI_AVAILABLE = False


CHECKLIST_URL = "https://www.dawtrina.com/music/frs/checklist.html"
OUTPUT_BASE = Path(
    "/media/andy/DATA/Projects/The Friday Rock Show Registry/FRSAudio/Source"
)
YEAR_MIN = 1978
YEAR_MAX = 1993

FANDOM_BASE_URL = "https://fridayrockshow.fandom.com"
REPO_ROOT = Path(__file__).resolve().parent.parent
FANDOM_DELAY = 1.0

DOWNLOAD_SOURCES: dict[str, str] = {
    "mega.nz": "Mega",
    "mediafire.com": "Mediafire",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "mixcloud.com": "Mixcloud",
}

_FANDOM_MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

FANDOM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_log_file: TextIO | None = None


def log(tag: str, msg: str) -> None:
    """Print a tagged diagnostic line to stdout and (if open) the log file."""
    line = f"[{tag}] {msg}"
    print(line, flush=True)
    if _log_file is not None:
        print(line, flush=True, file=_log_file)


# ---------------------------------------------------------------------------
# Mixcloud / dawtrina path
# ---------------------------------------------------------------------------

def parse_date(day_mon: str, year: int) -> str | None:
    """Convert '4 Jan' + 1980 → '1980-01-04'.  Returns None on any parse failure."""
    try:
        dt = datetime.strptime(f"{day_mon.strip()} {year}", "%d %b %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def fetch_episodes(year: int) -> list[tuple[str, str]]:
    """Fetch the dawtrina checklist and return (iso_date, mixcloud_url) pairs for *year*.

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

        if len(texts) == 1 and texts[0] == str(year):
            log("PARSE", f"Found year section marker: {year}")
            in_year = True
            continue

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

        if texts[0] == "#":
            continue

        if not texts[0].strip() or len(texts) < 4:
            continue

        total_rows_for_year += 1
        date_raw = texts[1].strip()

        iso_date = parse_date(date_raw, year)
        if iso_date is None:
            log("PARSE", f"  WARNING: could not parse date '{date_raw}' — skipping row")
            parse_errors += 1
            continue

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
# Fandom path — session
# ---------------------------------------------------------------------------

def build_fandom_session(cookies_file: Path):
    """Build a curl_cffi session with browser impersonation and Fandom cookies."""
    if not _CFFI_AVAILABLE:
        raise RuntimeError(
            "curl_cffi is required for the --fandom path.\n"
            "Install with:  pip install curl-cffi"
        )
    session = cffi_requests.Session(impersonate="chrome124")
    session.headers.update(FANDOM_HEADERS)

    if not cookies_file.exists():
        raise FileNotFoundError(
            f"Cookie file not found: {cookies_file}\n"
            "Export your browser cookies for fridayrockshow.fandom.com in Netscape "
            "format and save them as cookies.txt at the repo root."
        )

    jar = http.cookiejar.MozillaCookieJar(str(cookies_file))
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except http.cookiejar.LoadError as exc:
        raise RuntimeError(f"Failed to load cookies from {cookies_file}: {exc}") from exc

    session.cookies = jar  # type: ignore[assignment]
    return session


# ---------------------------------------------------------------------------
# Fandom path — scraping
# ---------------------------------------------------------------------------

def _fandom_parse_date(title: str) -> str | None:
    """Parse a wiki page title like '13_February_1987' → '1987-02-13'."""
    title = title.replace("_", " ")
    m = re.search(
        r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{4})",
        title,
        re.IGNORECASE,
    )
    if not m:
        return None
    day = int(m.group(1))
    month = _FANDOM_MONTHS[m.group(2).lower()]
    year_str = m.group(3)
    return f"{year_str}-{month}-{day:02d}"


def get_fandom_episode_links(session, year: int) -> list[tuple[str, str]]:
    """Return [(iso_date, '/wiki/DD_Month_YYYY'), ...] for *year* from the Fandom wiki."""
    year_url = f"{FANDOM_BASE_URL}/wiki/{year}"
    log("FANDOM", f"Fetching year index: {year_url}")

    resp = session.get(year_url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    section_heading = None
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        text = heading.get_text(strip=True).lower()
        if "shows shared" in text or "list of frs dates" in text:
            section_heading = heading
            log("FANDOM", f"Found section: '{heading.get_text(strip=True)}'")
            break

    if section_heading is None:
        raise RuntimeError(
            f"Could not find 'Shows Shared' or 'List of FRS Dates' section on {year_url}"
        )

    heading_level = int(section_heading.name[1])
    seen: set[str] = set()
    links: list[tuple[str, str]] = []

    for sibling in section_heading.find_next_siblings():
        if not isinstance(sibling, Tag):
            continue
        if sibling.name and re.match(r"^h[1-6]$", sibling.name):
            if int(sibling.name[1]) <= heading_level:
                break
        for a in sibling.find_all("a", href=True):
            raw_href = str(a.get("href", ""))
            parsed = urllib.parse.urlparse(raw_href)
            path = parsed.path or ""
            if not path.startswith("/wiki/"):
                continue
            title = urllib.parse.unquote(path.removeprefix("/wiki/"))
            if ":" in title or title.strip() == str(year):
                continue
            if parsed.fragment:
                continue
            iso_date = _fandom_parse_date(title)
            if iso_date is None:
                continue
            wiki_path = f"/wiki/{title}"
            if wiki_path not in seen:
                seen.add(wiki_path)
                links.append((iso_date, wiki_path))

    links.sort(key=lambda x: x[0])
    log("FANDOM", f"Found {len(links)} episode link(s) for year {year}")
    return links


def get_fandom_download_urls(session, episode_path: str) -> list[tuple[str, str]]:
    """Return [(source_label, url), ...] for all known download links on an episode page."""
    episode_url = f"{FANDOM_BASE_URL}{episode_path}"
    resp = session.get(episode_url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    seen_urls: set[str] = set()
    results: list[tuple[str, str]] = []

    for a in soup.find_all("a", href=True):
        href = str(a.get("href", ""))
        if href in seen_urls:
            continue
        for domain, label in DOWNLOAD_SOURCES.items():
            if domain in href:
                seen_urls.add(href)
                results.append((label, href))
                break

    return results


def fetch_fandom_episodes(
    year: int, session
) -> list[tuple[str, list[tuple[str, str]]]]:
    """Return [(iso_date, [(source_label, url), ...]), ...] for *year* from the Fandom wiki."""
    episode_links = get_fandom_episode_links(session, year)
    results: list[tuple[str, list[tuple[str, str]]]] = []

    total = len(episode_links)
    for idx, (iso_date, wiki_path) in enumerate(episode_links, start=1):
        log("FANDOM", f"[{idx}/{total}] Fetching episode page: {wiki_path}")
        time.sleep(FANDOM_DELAY)
        try:
            download_urls = get_fandom_download_urls(session, wiki_path)
        except Exception as exc:
            log("FANDOM", f"  WARNING: could not fetch {wiki_path}: {exc}")
            download_urls = []
        results.append((iso_date, download_urls))

    no_links = sum(1 for _, urls in results if not urls)
    log("FANDOM", f"Episode scrape complete: {total} episode(s), {no_links} with no download links")
    return results


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_episode(
    iso_date: str,
    url: str,
    out_path: Path,
    cookies_browser: str | None,
    source_label: str = "",
) -> bool:
    """Run yt-dlp to download *url* as MP3 to *out_path*.

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
    cmd.append(url)

    log("CMD", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        size_mb = out_path.stat().st_size / (1024 * 1024) if out_path.exists() else 0.0
        source_tag = f" [{source_label}]" if source_label else ""
        log("OK", f"Saved → {out_path}  ({size_mb:.1f} MB){source_tag}")
        return True

    stderr_lines = result.stderr.strip().splitlines() if result.stderr.strip() else []
    tail = stderr_lines[-5:] if len(stderr_lines) > 5 else stderr_lines
    source_tag = f"  [{source_label}]" if source_label else ""
    log("BROKEN", f"{iso_date}{source_tag}  {url}  (yt-dlp exit {result.returncode})")
    for line in tail:
        log("BROKEN", f"  yt-dlp: {line}")
    return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    global _log_file

    parser = argparse.ArgumentParser(
        description="Download Friday Rock Show MP3s from Mixcloud or the Fandom wiki.",
        epilog=(
            "Examples:\n"
            "  %(prog)s --year 1980\n"
            "  %(prog)s --year 1981 --month 03\n"
            "  %(prog)s --year 1980 --month 01 --dry-run\n"
            "  %(prog)s --year 1987 --fandom --dry-run\n"
            "  %(prog)s --year 1986 1987 1988 --fandom\n\n"
            "For the --fandom path, ensure cookies.txt (Netscape format) is at the repo root.\n"
            "For the Mixcloud path, supply --cookies-browser chrome to read saved login cookies."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--year", "-y",
        type=int,
        nargs="+",
        metavar="YEAR",
        required=True,
        help=f"One or more 4-digit broadcast years ({YEAR_MIN}–{YEAR_MAX})",
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
    parser.add_argument(
        "--fandom",
        action="store_true",
        help="Download from the Fandom wiki (Mega/Mediafire/YouTube/Mixcloud) instead of dawtrina.com",
    )
    parser.add_argument(
        "--cookies-file",
        metavar="PATH",
        default=str(REPO_ROOT / "cookies.txt"),
        help="Netscape cookies.txt for the Fandom wiki (default: <repo-root>/cookies.txt)",
    )
    args = parser.parse_args()

    years = sorted(set(args.year))
    for y in years:
        if not YEAR_MIN <= y <= YEAR_MAX:
            parser.error(f"year must be between {YEAR_MIN} and {YEAR_MAX}: got {y}")

    month_filter: int | None = None
    month_label = "all months"
    if args.month:
        if not (args.month.isdigit() and 1 <= int(args.month) <= 12):
            parser.error("--month must be a two-digit value between 01 and 12")
        month_filter = int(args.month)
        month_label = f"month {args.month}"

    source_name = "Fandom wiki" if args.fandom else "dawtrina.com / Mixcloud"

    # Build fandom session once for all years
    fandom_session = None
    if args.fandom:
        try:
            fandom_session = build_fandom_session(Path(args.cookies_file))
        except (FileNotFoundError, RuntimeError) as exc:
            print(f"[FAIL] {exc}", flush=True)
            return 1

    grand_episodes = grand_downloaded = grand_skipped = grand_failed = 0
    grand_no_links = grand_broken = 0
    any_failed = False

    for year in years:
        out_dir = OUTPUT_BASE / str(year)

        if args.fandom:
            out_dir.mkdir(parents=True, exist_ok=True)
            log_path = out_dir / f"download-fandom-{year}.log"
            _log_file = log_path.open("a", encoding="utf-8")

        try:
            log("START", "=" * 60)
            log("START", "Friday Rock Show episode downloader")
            log("START", f"  Year   : {year}")
            log("START", f"  Months : {month_label}")
            log("START", f"  Output : {out_dir}")
            log("START", f"  Source : {source_name}")
            log("START", f"  Dry run: {args.dry_run}")
            if args.cookies_browser:
                log("START", f"  Cookies: from browser '{args.cookies_browser}'")
            if args.fandom:
                log("START", f"  Cookies file: {args.cookies_file}")
                log("START", f"  Log file    : {out_dir / f'download-fandom-{year}.log'}")
            log("START", "=" * 60)

            # ── Fandom path ────────────────────────────────────────────────────
            if args.fandom:
                try:
                    fandom_episodes = fetch_fandom_episodes(year, fandom_session)
                except Exception as exc:
                    log("FAIL", f"Could not retrieve Fandom episode list: {exc}")
                    any_failed = True
                    continue

                if month_filter is not None:
                    before = len(fandom_episodes)
                    fandom_episodes = [
                        (d, urls)
                        for d, urls in fandom_episodes
                        if datetime.fromisoformat(d).month == month_filter
                    ]
                    log(
                        "PARSE",
                        f"Month filter ({args.month}): {before} → {len(fandom_episodes)} episode(s)",
                    )

                total = len(fandom_episodes)
                if total == 0:
                    log("DONE", f"No episodes found for year={year} month={args.month}.")
                    continue

                log("START", f"{total} episode(s) to process")
                if not args.dry_run:
                    out_dir.mkdir(parents=True, exist_ok=True)

                downloaded = skipped = failed = no_links = broken_links = 0

                for idx, (iso_date, source_url_pairs) in enumerate(fandom_episodes, start=1):
                    log(f"DOWNLOAD {idx}/{total}", f"Date: {iso_date}")

                    if not source_url_pairs:
                        log("SKIP", f"{iso_date} — no download links found on episode page")
                        no_links += 1
                        skipped += 1
                        continue

                    source_names = ", ".join(label for label, _ in source_url_pairs)
                    log(f"DOWNLOAD {idx}/{total}", f"Files : {len(source_url_pairs)} ({source_names})")
                    for file_idx, (src, url) in enumerate(source_url_pairs, start=1):
                        log(f"DOWNLOAD {idx}/{total}", f"File {file_idx}: {src}  → {url}")

                    multi = len(source_url_pairs) > 1
                    episode_downloaded = episode_failed = 0

                    for file_idx, (src, url) in enumerate(source_url_pairs, start=1):
                        filename = f"FRS {iso_date} ({file_idx}).mp3" if multi else f"FRS {iso_date}.mp3"
                        out_path = out_dir / filename

                        if out_path.exists():
                            size_mb = out_path.stat().st_size / (1024 * 1024)
                            log("SKIP", f"Already exists ({size_mb:.1f} MB) — {out_path}")
                            skipped += 1
                            continue

                        if args.dry_run:
                            log("OK", f"[DRY-RUN] [{src}] Would download → {out_path}")
                            episode_downloaded += 1
                            continue

                        try:
                            success = download_episode(
                                iso_date, url, out_path, args.cookies_browser, src
                            )
                        except FileNotFoundError:
                            log("FAIL", "yt-dlp executable not found on PATH.")
                            log("FAIL", "  Install with:  sudo apt install yt-dlp")
                            log("FAIL", "            or:  pip install yt-dlp")
                            return 1
                        except Exception as exc:
                            log("FAIL", f"{iso_date} [{src}]: unexpected error: {exc}")
                            episode_failed += 1
                            continue

                        if success:
                            episode_downloaded += 1
                        else:
                            episode_failed += 1
                            broken_links += 1

                    downloaded += episode_downloaded
                    failed += episode_failed

                log("DONE", "=" * 60)
                log("DONE", f"Run complete for year={year}  months={month_label}  source=Fandom")
                log("DONE", f"  Downloaded    : {downloaded}")
                log("DONE", f"  Skipped       : {skipped}  (already on disk or no links)")
                log("DONE", f"  No links found: {no_links}")
                log("DONE", f"  Broken links  : {broken_links}")
                log("DONE", f"  Failed        : {failed}")
                log("DONE", f"  Total episodes: {total}")
                log("DONE", "=" * 60)

                grand_episodes += total
                grand_downloaded += downloaded
                grand_skipped += skipped
                grand_failed += failed
                grand_no_links += no_links
                grand_broken += broken_links
                if failed > 0:
                    any_failed = True

            else:
                # ── Mixcloud / dawtrina path ───────────────────────────────────
                try:
                    episodes = fetch_episodes(year)
                except Exception as exc:
                    log("FAIL", f"Could not retrieve episode list: {exc}")
                    any_failed = True
                    continue

                if not episodes:
                    log("DONE", f"No episodes with Mixcloud links found for year {year}.")
                    continue

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
                    log("DONE", f"No episodes found for year={year} month={args.month}.")
                    continue

                log("START", f"{len(episodes)} episode(s) to process")

                if not args.dry_run:
                    out_dir.mkdir(parents=True, exist_ok=True)
                    log("START", f"Output directory ready: {out_dir}")

                total = len(episodes)
                downloaded = skipped = failed = 0

                for idx, (iso_date, mixcloud_url) in enumerate(episodes, start=1):
                    filename = f"FRS {iso_date}.mp3"
                    out_path = out_dir / filename

                    log(f"DOWNLOAD {idx}/{total}", f"Date: {iso_date}")
                    log(f"DOWNLOAD {idx}/{total}", f"URL : {mixcloud_url}")
                    log(f"DOWNLOAD {idx}/{total}", f"File: {out_path}")

                    if out_path.exists():
                        size_mb = out_path.stat().st_size / (1024 * 1024)
                        log("SKIP", f"Already exists ({size_mb:.1f} MB) — {out_path}")
                        skipped += 1
                        continue

                    if args.dry_run:
                        log("OK", f"[DRY-RUN] Would download → {out_path}")
                        downloaded += 1
                        continue

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

                log("DONE", "=" * 60)
                log("DONE", f"Run complete for year={year}  months={month_label}")
                log("DONE", f"  Downloaded : {downloaded}")
                log("DONE", f"  Skipped    : {skipped}  (already on disk)")
                log("DONE", f"  Failed     : {failed}")
                log("DONE", f"  Total      : {total}")
                log("DONE", "=" * 60)

                grand_episodes += total
                grand_downloaded += downloaded
                grand_skipped += skipped
                grand_failed += failed
                if failed > 0:
                    any_failed = True

        finally:
            if _log_file is not None:
                _log_file.close()
                _log_file = None

    # Grand total across all years (stdout only; per-year log files already closed)
    if len(years) > 1:
        year_range = ", ".join(str(y) for y in years)
        print(f"[TOTAL] {'=' * 60}", flush=True)
        print(f"[TOTAL] Grand total across {len(years)} year(s): {year_range}", flush=True)
        if args.fandom:
            print(f"[TOTAL]   Downloaded    : {grand_downloaded}", flush=True)
            print(f"[TOTAL]   Skipped       : {grand_skipped}  (already on disk or no links)", flush=True)
            print(f"[TOTAL]   No links found: {grand_no_links}", flush=True)
            print(f"[TOTAL]   Broken links  : {grand_broken}", flush=True)
            print(f"[TOTAL]   Failed        : {grand_failed}", flush=True)
            print(f"[TOTAL]   Total episodes: {grand_episodes}", flush=True)
        else:
            print(f"[TOTAL]   Downloaded : {grand_downloaded}", flush=True)
            print(f"[TOTAL]   Skipped    : {grand_skipped}  (already on disk)", flush=True)
            print(f"[TOTAL]   Failed     : {grand_failed}", flush=True)
            print(f"[TOTAL]   Total      : {grand_episodes}", flush=True)
        print(f"[TOTAL] {'=' * 60}", flush=True)

    return 0 if not any_failed else 1


if __name__ == "__main__":
    sys.exit(main())
