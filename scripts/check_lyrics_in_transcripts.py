#!/usr/bin/env python3
"""Check transcripts for verbatim lyric matches using the Genius API.

Usage:
  GENIUS_API_TOKEN must be set in the environment.
  python scripts/check_lyrics_in_transcripts.py --episode data/episodes/1980/FRS\ 1980-01-04.json

The script writes a JSON report to `logs/lyrics_flags.json` by default.
"""
import argparse
import os
import json
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher


GENIUS_SEARCH_URL = "https://api.genius.com/search"
GENIUS_BASE = "https://genius.com"


def normalize(text: str) -> str:
    text = text or ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def genius_search(song_title: str, artist: Optional[str], token: str) -> Optional[str]:
    headers = {"Authorization": f"Bearer {token}"}
    params = {"q": f"{song_title} {artist or ''}"}
    resp = requests.get(GENIUS_SEARCH_URL, headers=headers, params=params, timeout=10)
    if resp.status_code != 200:
        return None
    data = resp.json()
    hits = data.get("response", {}).get("hits", [])
    if not hits:
        return None
    # Prefer exact title match if possible
    for h in hits:
        result = h.get("result", {})
        if normalize(result.get("title", "")) == normalize(song_title):
            return result.get("url")
    # otherwise return first hit url
    return hits[0].get("result", {}).get("url")


def fetch_lyrics_from_genius_url(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "lyrics-checker/1.0"})
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        # Genius uses a few possible containers; try common ones
        lyrics_div = soup.find("div", class_=re.compile(r"Lyrics__Root|lyrics"))
        if lyrics_div:
            # Get text from children
            return lyrics_div.get_text(separator="\n").strip()
        # fallback: select all <p> within .lyrics or look for data-lyrics-container
        parts = soup.select("[data-lyrics-container]")
        if parts:
            return "\n".join(p.get_text(separator=" ") for p in parts).strip()
        # last resort: meta description
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"]
    except Exception:
        return None
    return None


def any_lyrics_snippet_in_transcript(lyrics: str, transcript_segments: List[Dict[str, Any]], n_words: int = 5, fuzzy_thresh: float = 0.9) -> Optional[Dict[str, Any]]:
    """Return a match dict including the transcript segment start if found.

    Scans each transcript segment separately so we can report the `start` attribute
    of the matched element in the source JSON.
    """
    if not lyrics or not transcript_segments:
        return None
    norm_lyrics = normalize(lyrics)
    words = norm_lyrics.split()
    if len(words) < n_words:
        return None

    # Precompute snippets from lyrics
    snippets = [" ".join(words[i : i + n_words]) for i in range(0, max(1, len(words) - n_words + 1))]

    # Check each transcript segment individually and return the first hit with its start
    for seg in transcript_segments:
        seg_text = seg.get("text", "")
        seg_start = seg.get("start")
        norm_seg = normalize(seg_text)
        if not norm_seg:
            continue
        for snippet in snippets:
            if snippet in norm_seg:
                return {"match": snippet, "type": "exact", "transcript_start": seg_start}
            # fuzzy check: compare snippet to the segment (cheap heuristic)
            ratio = SequenceMatcher(None, snippet, norm_seg[: len(snippet)]).ratio()
            if ratio >= fuzzy_thresh:
                return {"match": snippet, "type": "fuzzy", "ratio": ratio, "transcript_start": seg_start}
    return None


def process_episode_file(path: Path, token: str, write_back: bool = False) -> List[Dict[str, Any]]:
    out_flags = []
    with path.open("r", encoding="utf-8") as fh:
        ep = json.load(fh)

    transcript_segments = ep.get("transcript") or []

    track_listing = ep.get("track_listing") or []
    for idx, t in enumerate(track_listing):
        artist = t.get("artist")
        title = t.get("track") or t.get("title") or t.get("song")
        if not title:
            continue
        time.sleep(0.5)
        url = genius_search(title, artist, token)
        lyrics = None
        if url:
            lyrics = fetch_lyrics_from_genius_url(url)
        # if no lyrics, skip
        if not lyrics:
            continue
        match = any_lyrics_snippet_in_transcript(lyrics, transcript_segments)
        if match:
            flag = {
                "episode": path.as_posix(),
                "track_index": idx,
                "artist": artist,
                "title": title,
                "genius_url": url,
                "matched_snippet": match.get("match"),
                "match_type": match.get("type"),
                "transcript_start": match.get("transcript_start"),
            }
            out_flags.append(flag)
            if write_back:
                t["lyrics_flag"] = True
                t["lyrics_match_snippet"] = match.get("match")

    if write_back and out_flags:
        with path.open("w", encoding="utf-8") as fh:
            json.dump(ep, fh, ensure_ascii=False, indent=2)

    return out_flags


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--episode", help="Single episode JSON file to check")
    p.add_argument("--episodes-dir", help="Directory of episode JSON files", default="data/episodes")
    p.add_argument("--output", help="Output JSON report file", default="logs/lyrics_flags.json")
    p.add_argument("--write", help="Write flags back into episode JSON files", action="store_true")
    args = p.parse_args()

    token = os.environ.get("GENIUS_API_TOKEN")
    if not token:
        print("GENIUS_API_TOKEN not set. Export it and retry.")
        raise SystemExit(1)

    out = []
    if args.episode:
        path = Path(args.episode)
        if not path.exists():
            print(f"Episode not found: {path}")
            raise SystemExit(2)
        out.extend(process_episode_file(path, token, write_back=args.write))
    else:
        base = Path(args.episodes_dir)
        for fn in sorted(base.rglob("*.json")):
            out.extend(process_episode_file(fn, token, write_back=args.write))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"Wrote {len(out)} flags to {out_path}")


if __name__ == "__main__":
    main()
