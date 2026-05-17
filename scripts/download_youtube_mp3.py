#!/usr/bin/env python3
"""
Download audio from a YouTube video as a 128 kbps MP3.

Usage:
    python scripts/download_youtube_mp3.py <youtube_url> [--output-dir <dir>]

Requires:
    - yt-dlp  (pip install yt-dlp)
    - ffmpeg  (system package: sudo apt install ffmpeg)
"""

import argparse
import sys
from pathlib import Path
from typing import Any, cast

try:
    import yt_dlp
except ImportError:
    sys.exit("yt-dlp not found. Install it with: pip install yt-dlp")


def download_mp3(url: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts: dict[str, Any] = {
        # Extract audio only and convert to MP3
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }
        ],
        # Save as <title>.mp3 inside output_dir
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        # Show a clean progress bar
        "quiet": False,
        "no_warnings": False,
    }

    with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "unknown")
        print(f"\nDownloaded: {title}")
        print(f"Saved to:   {output_dir.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download YouTube audio as MP3.")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--output-dir",
        default="FRSAudio/youtube",
        help="Directory to save the MP3 (default: FRSAudio/youtube)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    download_mp3(args.url, output_dir)


if __name__ == "__main__":
    main()
