#!/usr/bin/env python3
"""
FRS Episode Detail Extractor (integrated into AskTV repo)

Placed under `scripts/` with defaults that write into the repo's
`data/episodes/<YEAR>/` and look for `cookies.txt` at the repo root.
"""

import argparse
import http.cookiejar
import json
import re
import time
import urllib.parse
from pathlib import Path

from curl_cffi import requests
from bs4 import BeautifulSoup, FeatureNotFound, Tag

# Prefer lxml if available; otherwise fall back to the built-in parser.
try:
    PARSER = "lxml"
except Exception:
    PARSER = "html.parser"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://fridayrockshow.fandom.com"
YEAR: str | None = None
REPO_ROOT = Path(__file__).resolve().parent.parent
COOKIES_FILE = REPO_ROOT / "cookies.txt"
OUTPUT_DIR: Path | None = None
SKIP_EXISTING: bool = False
DELAY_SECONDS = 1.0          # polite delay between requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}

SECTIONS = {
    "Show": "show",
    "Sessions": "sessions",
    "Track Listing": "track_listing",
}


def build_session() -> requests.Session:
    session = requests.Session(impersonate="chrome124")
    session.headers.update(HEADERS)

    if not COOKIES_FILE.exists():
        raise FileNotFoundError(
            f"Cookie file not found: {COOKIES_FILE}\n"
            "Please export your browser cookies for fridayrockshow.fandom.com "
            "in Netscape format and save them as cookies.txt at the repo root."
        )

    jar = http.cookiejar.MozillaCookieJar(str(COOKIES_FILE))
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except http.cookiejar.LoadError as exc:
        raise RuntimeError(
            f"Failed to load cookies from {COOKIES_FILE}: {exc}\n"
            "Ensure the file is in Netscape/Mozilla cookies.txt format."
        ) from exc

    session.cookies = jar  # type: ignore[assignment]
    return session


def get_episode_links(session: requests.Session) -> list[str]:
    year_url = f"{BASE_URL}/wiki/{YEAR}"
    print(f"Fetching year index: {year_url}")

    resp = session.get(year_url, timeout=30)
    resp.raise_for_status()

    try:
        soup = BeautifulSoup(resp.text, PARSER)
    except FeatureNotFound:
        print("WARNING: requested parser not available; falling back to html.parser")
        soup = BeautifulSoup(resp.text, "html.parser")

    section_heading = None
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        if "list of frs dates" in heading.get_text(strip=True).lower():
            section_heading = heading
            break

    if section_heading is None:
        raise RuntimeError("Could not find the 'List Of FRS Dates' section on the year page.")

    heading_level_num = int(section_heading.name[1])
    links: set[str] = set()

    for sibling in section_heading.find_next_siblings():
        # Only consider Tag siblings; skip strings or other nodes
        if not isinstance(sibling, Tag):
            continue

        if sibling.name and re.match(r"^h[1-6]$", sibling.name):
            if int(sibling.name[1]) <= heading_level_num:
                break

        for a in sibling.find_all("a", href=True):
            raw_href = a.get("href", "")
            # Normalize and parse the href to handle absolute and relative links
            parsed = urllib.parse.urlparse(str(raw_href))
            path = parsed.path or ""

            # Only accept internal wiki paths
            if not path.startswith("/wiki/"):
                continue

            # Extract the wiki title part and decode percent-escapes
            title = urllib.parse.unquote(path.removeprefix("/wiki/"))

            # Skip namespace or special pages (contain a colon), and skip the year index itself
            if ":" in title or title.strip() == YEAR:
                continue

            # Skip links that are only anchors or contain fragments
            if parsed.fragment:
                continue

            links.add(f"/wiki/{title}")

    if not links:
        raise RuntimeError("No episode links were found in the 'List Of FRS Dates' section.")

    sorted_links = sorted(links)
    print(f"Found {len(sorted_links)} episode link(s).")
    return sorted_links


def fetch_wikitext(session: requests.Session, page_path: str) -> str | None:
    page_name = urllib.parse.unquote(page_path.removeprefix("/wiki/"))
    api_url = f"{BASE_URL}/api.php"
    params = {
        "action": "parse",
        "page": page_name,
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2",
    }

    resp = session.get(api_url, params=params, timeout=30)
    if resp.status_code != 200:
        print(f"  WARNING: HTTP {resp.status_code} for {page_path} — skipping.")
        return None

    data = resp.json()
    if "error" in data:
        print(f"  WARNING: API error for {page_path}: {data['error'].get('info', data['error'])} — skipping.")
        return None

    return data.get("parse", {}).get("wikitext", "")


def parse_sections(wikitext: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {key: [] for key in SECTIONS.values()}
    section_pattern = re.compile(r"^={2,3}\s*(.+?)\s*={2,3}\s*$", re.MULTILINE)
    matches = list(section_pattern.finditer(wikitext))

    for i, match in enumerate(matches):
        heading_text = match.group(1).strip()
        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(wikitext)
        body = wikitext[body_start:body_end]
        for wiki_heading, json_key in SECTIONS.items():
            if heading_text.lower() == wiki_heading.lower():
                bullets = []
                for line in body.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("*"):
                        bullet_text = re.sub(r"^\*+\s*", "", stripped)
                        bullet_text = strip_wikitext_markup(bullet_text)
                        if bullet_text:
                            bullets.append(bullet_text)
                result[json_key] = bullets
                break

    return result


def strip_wikitext_markup(text: str) -> str:
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    text = re.sub(r"'{2,3}", "", text)
    text = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def parse_session_line(line: str) -> dict:
    if not line:
        return {"artist": None, "details": None}
    delimiters = [',', '.', '#']
    positions = [(line.find(d), d) for d in delimiters if line.find(d) != -1]
    if positions:
        pos, delim = min(positions, key=lambda x: x[0])
        artist = line[:pos].strip()
        details = line[pos + 1 :].strip()
        artist = re.sub(r"\s*#\d+$", "", artist).strip()
        if re.search(r"recorded\.?$", artist, re.IGNORECASE):
            artist = re.sub(r"(?:\s*#\d+)?\.?\s*recorded\.?$", "", artist, flags=re.IGNORECASE).strip()
            details = ("recorded " + details) if details else "recorded"
        return {"artist": artist or None, "details": details or None}
    if "," in line:
        artist, details = line.split(",", 1)
        artist = re.sub(r"\s*#\d+$", "", artist.strip()).strip()
        return {"artist": artist or None, "details": details.strip() or None}
    if " - " in line:
        artist, details = line.split(" - ", 1)
        artist = re.sub(r"\s*#\d+$", "", artist.strip()).strip()
        return {"artist": artist or None, "details": details.strip() or None}
    if ":" in line:
        artist, details = line.split(":", 1)
        artist = re.sub(r"\s*#\d+$", "", artist.strip()).strip()
        return {"artist": artist or None, "details": details.strip() or None}
    parts = line.split(None, 1)
    if len(parts) == 2:
        return {"artist": parts[0].strip(), "details": parts[1].strip()}
    return {"artist": None, "details": line.strip()}


def parse_track_line(line: str) -> dict:
    if not line:
        return {"artist": None, "track": None, "details": None}
    if ":" not in line:
        return {"artist": None, "track": line.strip(), "details": None}
    artist_part, rest = line.split(":", 1)
    artist = artist_part.strip()
    rest = rest.strip()
    m = re.match(r"^'([^']+)'\s*(?:\(([^)]+)\))?\s*(?:\(([^)]+)\))?$", rest)
    if m:
        track_text = m.group(1).strip()
        paren1 = m.group(2)
        paren2 = m.group(3)
        details_parts = [p for p in (paren1, paren2) if p]
        m2 = re.match(r"^(.*)\s*\(([^)]+)\)\s*$", track_text)
        if m2:
            track = m2.group(1).strip()
            details_parts.insert(0, m2.group(2).strip())
        else:
            track = track_text
        details = "; ".join(details_parts) if details_parts else None
        return {"artist": artist, "track": track, "details": details}
    m = re.match(r'^"([^\"]+)"\s*(?:\(([^)]+)\))?\s*(?:\(([^)]+)\))?$', rest)
    if m:
        track_text = m.group(1).strip()
        paren1 = m.group(2)
        paren2 = m.group(3)
        details_parts = [p for p in (paren1, paren2) if p]
        m2 = re.match(r"^(.*)\s*\(([^)]+)\)\s*$", track_text)
        if m2:
            track = m2.group(1).strip()
            details_parts.insert(0, m2.group(2).strip())
        else:
            track = track_text
        details = "; ".join(details_parts) if details_parts else None
        return {"artist": artist, "track": track, "details": details}
    m = re.match(r"^([^\(]+?)\s*(?:\(([^)]+)\))?\s*$", rest)
    if m:
        track_text = m.group(1).strip()
        paren = m.group(2)
        m2 = re.match(r"^(.*)\s*\(([^)]+)\)\s*$", track_text)
        details_parts = []
        if m2:
            track = m2.group(1).strip()
            details_parts.append(m2.group(2).strip())
        else:
            track = track_text
        if paren:
            details_parts.append(paren.strip())
        details = "; ".join(details_parts) if details_parts else None
        return {"artist": artist, "track": track, "details": details}
    return {"artist": artist, "track": rest, "details": None}


def _extract_date_from_path(page_path: str) -> str | None:
    page_name = urllib.parse.unquote(page_path.removeprefix("/wiki/"))
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", page_name)
    if date_match:
        return date_match.group(1)
    return None


_MONTHS = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}


def _parse_date_from_text(text: str) -> str | None:
    if not text:
        return None
    iso = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if iso:
        return iso.group(1)
    m = re.search(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", text, re.IGNORECASE)
    if m:
        day = int(m.group(1))
        month = _MONTHS[m.group(2).lower()]
        year = m.group(3)
        return f"{year}-{month}-{day:02d}"
    return None


def extract_comments_from_show(show_lines: list[str], date_str: str | None) -> list[str]:
    comments: list[str] = []
    for line in show_lines:
        if not line or not line.strip():
            continue
        if date_str and date_str in line:
            continue
        if re.search(r"\d{4}-\d{2}-\d{2}", line):
            continue
        comments.append(line)
    return comments


def create_stubs_from_audio(output_dir: Path, year: str) -> int:
    """Scan FRSAudio/Source/{year} for MP3s without JSON and create stubs.

    Returns the number of stub files created.
    """
    if not year:
        return 0
    audio_dir = REPO_ROOT.parent / "FRSAudio" / "Source" / str(year)
    if not audio_dir.exists():
        print(f"  Audio source directory not found: {audio_dir}")
        return 0

    pattern = re.compile(r"FRS\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
    created = 0

    for p in sorted(audio_dir.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() != ".mp3":
            continue
        m = pattern.search(p.name)
        if not m:
            continue
        date_str = m.group(1)
        json_name = f"FRS {date_str}.json"
        json_path = output_dir / json_name
        if json_path.exists():
            continue

        stub = {
            "title": f"FRS {date_str}",
            "url": "",
            "show": {"date": date_str, "comments": []},
            "sessions": [],
            "track_listing": [],
        }
        try:
            with json_path.open("w", encoding="utf-8") as fh:
                json.dump(stub, fh, ensure_ascii=False, indent=2)
            print(f"  Stub created: {json_name} (from {p.name})")
            created += 1
        except Exception as exc:
            print(f"  WARNING: could not write stub {json_name}: {exc}")

    return created


def main() -> None:
    if OUTPUT_DIR is None:
        raise RuntimeError("OUTPUT_DIR is not set — please provide a year via --year")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session = build_session()
    episode_links = get_episode_links(session)
    success_count = 0
    skip_count = 0
    for page_path in episode_links:
        episode_url = f"{BASE_URL}{page_path}"
        print(f"Processing: {episode_url}")
        time.sleep(DELAY_SECONDS)
        wikitext = fetch_wikitext(session, page_path)
        if wikitext is None:
            skip_count += 1
            continue
        sections = parse_sections(wikitext)
        raw_sessions = sections.get("sessions", [])
        processed_sessions = [parse_session_line(s) for s in raw_sessions]
        raw_tracks = sections.get("track_listing", [])
        processed_tracks = [parse_track_line(t) for t in raw_tracks]
        date_str = _extract_date_from_path(page_path)
        if not date_str:
            show_text = " ".join(sections.get("show", []))
            date_str = _parse_date_from_text(show_text)
        if not date_str:
            print(f"  WARNING: could not determine YYYY-MM-DD date for {page_path}; skipping.")
            skip_count += 1
            continue
        filename = f"FRS {date_str}.json"
        output_path = OUTPUT_DIR / filename
        if SKIP_EXISTING and output_path.exists():
            print(f"  Skipping existing: {output_path.name}")
            skip_count += 1
            continue
        comments = extract_comments_from_show(sections.get("show", []), date_str)
        episode_data = {
            "title": f"FRS {date_str}",
            "url": episode_url,
            "show": {
                "date": date_str,
                "comments": comments,
            },
            "sessions": processed_sessions,
            "track_listing": processed_tracks,
        }
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(episode_data, fh, ensure_ascii=False, indent=2)
        print(f"  Written: {output_path.name}")
        success_count += 1
    print(f"\nDone. {success_count} episode(s) written to {OUTPUT_DIR}, {skip_count} skipped.")
    # After creating JSONs from the wiki, scan the audio source folder for
    # MP3 files that don't yet have a corresponding JSON and create stub files.
    try:
        created = create_stubs_from_audio(OUTPUT_DIR, YEAR)
        if created:
            print(f"Created {created} stub JSON file(s) for audio-only episodes.")
    except Exception as exc:  # defensive: don't fail the whole run for this
        print(f"  WARNING: failed to create stub JSONs from audio: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FRS episode extractor — requires a year argument (e.g. 1980)")
    parser.add_argument("--year", "-y", required=True, help="Year to extract (YYYY)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip writing JSON files that already exist")
    args = parser.parse_args()

    # Validate year format
    if not re.fullmatch(r"\d{4}", args.year):
        raise SystemExit("Error: --year must be a 4-digit year, e.g. 1980")

    YEAR = args.year
    OUTPUT_DIR = REPO_ROOT / "data" / "episodes" / str(YEAR)
    if getattr(args, "skip_existing", False):
        SKIP_EXISTING = True
    print(f"Extractor running for year: {YEAR}")
    main()
