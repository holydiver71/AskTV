#!/usr/bin/env python3
"""Convert audio files to 128kbps MP3 for the AskTV pipeline.

This script finds audio files under an input directory and produces
128kbps MP3 files in the output directory preserving the
relative directory structure. It shells out to `ffmpeg`.

Example:
  python scripts/convert.py --input ../FRSAudio/Source --output ../FRSAudio/128kbps --bitrate 128k

Requirements:
  - ffmpeg available on PATH

Use this before running transcription if your source audio isn't already
encoded as 128kbps MP3 files used by the rest of the pipeline.
"""
import argparse
import subprocess
from pathlib import Path
import sys


def convert_file(src: Path, dst: Path, bitrate: str, dry_run: bool) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    # show the file being converted immediately for progress visibility
    print(f"converting: {src} -> {dst}", flush=True)
    cmd = [
        "ffmpeg",
        "-i",
        str(src),
        "-vn",
        "-ab",
        bitrate,
        "-map_metadata",
        "-1",
        str(dst),
    ]
    if dry_run:
        print("DRY-RUN:", " ".join(cmd))
        return True
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        print(f"converted: {src} -> {dst}")
        return True
    except subprocess.CalledProcessError:
        print(f"ERROR converting: {src}")
        return False


def main() -> int:
    p = argparse.ArgumentParser(description="Convert audio files to 128kbps MP3")
    p.add_argument("--input", "-i", required=True, help="Input directory containing source audio")
    p.add_argument("--output", "-o", required=True, help="Output directory for 128kbps MP3s")
    p.add_argument("--bitrate", "-b", default="128k", help="Target audio bitrate (default: 128k)")
    p.add_argument("--ext", "-e", default=".mp3", help="Output file extension (default: .mp3)")
    p.add_argument("--dry-run", action="store_true", help="Show commands without running ffmpeg")
    p.add_argument("--recursive", action="store_true", help="Recurse into subdirectories")
    p.add_argument("--overwrite", "-f", action="store_true", help="Overwrite existing output files (default: skip existing)")
    args = p.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    if not input_dir.exists():
        print("Input directory does not exist:", input_dir)
        return 2

    patterns = ["*.wav", "*.flac", "*.m4a", "*.mp3", "*.aac", "*.ogg"]
    files = []
    if args.recursive:
        for pat in patterns:
            files.extend(input_dir.rglob(pat))
    else:
        for pat in patterns:
            files.extend(input_dir.glob(pat))

    files = sorted([f for f in files if f.is_file()])
    if not files:
        print("No input audio files found in:", input_dir)
        return 0

    failed = 0
    for src in files:
        rel = src.relative_to(input_dir)
        # derive a readable bitrate label (e.g. '128k' -> '128kps')
        bit_label = args.bitrate
        if bit_label.endswith("k"):
            bit_label = bit_label[:-1] + "kps"
        else:
            bit_label = bit_label.replace(" ", "").replace("/", "_")

        dst = output_dir.joinpath(rel.parent, f"{rel.stem}_{bit_label}{args.ext}")
        if dst.exists() and not args.overwrite:
            print(f"skipping (exists): {dst}")
            continue
        ok = convert_file(src, dst, args.bitrate, args.dry_run)
        if not ok:
            failed += 1

    if failed:
        print(f"{failed} files failed to convert")
        return 3
    print("All done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
