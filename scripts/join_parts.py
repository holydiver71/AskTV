#!/usr/bin/env python3
"""Join split (Pt1 / Pt2) MP3 episodes into a single file for a given year.

Scans the Source/{year} folder for pairs of files matching the pattern
'FRS YYYY-MM-DD Pt1*.mp3' and 'FRS YYYY-MM-DD Pt2*.mp3' (case-insensitive)
and concatenates each pair into 'FRS YYYY-MM-DD.mp3' in the same folder
using ffmpeg's concat demuxer (lossless — no re-encoding).

Example:
  python scripts/join_parts.py --year 1979
  python scripts/join_parts.py --year 1979 --dry-run
  python scripts/join_parts.py --year 1979 --overwrite

Requirements:
  - ffmpeg available on PATH
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE_ROOT = Path(
    "/media/andy/DATA/Projects/The Friday Rock Show Registry/FRSAudio/Source"
)

DATE_RE = re.compile(r"^FRS (\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)


def find_pairs(folder: Path) -> list[tuple[str, Path, Path]]:
    """Return a sorted list of (date_str, pt1_path, pt2_path) tuples."""
    pt1_map: dict[str, Path] = {}
    pt2_map: dict[str, Path] = {}

    for f in folder.iterdir():
        if not f.is_file():
            continue
        name_lower = f.name.lower()
        m = DATE_RE.match(f.name)
        if not m:
            continue
        date_str = m.group(1)
        # Match 'pt1' or 'pt2' anywhere after the date (handles extra text in name)
        if "pt1" in name_lower:
            pt1_map[date_str] = f
        elif "pt2" in name_lower:
            pt2_map[date_str] = f

    pairs: list[tuple[str, Path, Path]] = []
    for date_str, pt1 in sorted(pt1_map.items()):
        if date_str not in pt2_map:
            print(f"WARNING: Pt1 found but no Pt2 for {date_str} — skipping")
            continue
        pairs.append((date_str, pt1, pt2_map[date_str]))

    # Warn about any orphaned Pt2 files
    for date_str in sorted(pt2_map):
        if date_str not in pt1_map:
            print(f"WARNING: Pt2 found but no Pt1 for {date_str} — skipping")

    return pairs


def join_pair(
    pt1: Path,
    pt2: Path,
    out_path: Path,
    dry_run: bool,
) -> bool:
    """Concatenate pt1 + pt2 into out_path using ffmpeg concat demuxer."""
    print(f"joining: {pt1.name} + {pt2.name} -> {out_path.name}", flush=True)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, dir=pt1.parent
    ) as tmp:
        tmp_path = Path(tmp.name)
        # ffmpeg concat list — paths must be escaped for the concat demuxer
        tmp.write(f"file '{pt1.name}'\n")
        tmp.write(f"file '{pt2.name}'\n")

    cmd = [
        "ffmpeg",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(tmp_path),
        "-c",
        "copy",
        str(out_path),
    ]

    if dry_run:
        print("DRY-RUN:", " ".join(cmd))
        tmp_path.unlink(missing_ok=True)
        return True

    try:
        subprocess.run(
            cmd,
            check=True,
            cwd=str(pt1.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        print(f"joined:  {out_path.name}")
        return True
    except subprocess.CalledProcessError:
        print(f"ERROR joining: {pt1.name} + {pt2.name}")
        return False
    finally:
        tmp_path.unlink(missing_ok=True)


def main() -> int:
    """Parse arguments and join all Pt1/Pt2 pairs for the given year."""
    parser = argparse.ArgumentParser(
        description="Join split Pt1/Pt2 MP3 episodes into single files"
    )
    parser.add_argument(
        "--year",
        required=True,
        type=int,
        metavar="YYYY",
        help="4-digit year to process (e.g. 1979)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print ffmpeg commands without executing them",
    )
    parser.add_argument(
        "--overwrite",
        "-f",
        action="store_true",
        help="Overwrite existing output files (default: skip)",
    )
    args = parser.parse_args()

    folder = SOURCE_ROOT / str(args.year)
    if not folder.is_dir():
        print(f"ERROR: folder not found: {folder}")
        return 1

    pairs = find_pairs(folder)
    if not pairs:
        print(f"No Pt1/Pt2 pairs found in {folder}")
        return 0

    print(f"Found {len(pairs)} pair(s) in {folder}\n")

    success = 0
    skipped = 0
    failed = 0

    for date_str, pt1, pt2 in pairs:
        out_path = folder / f"FRS {date_str}.mp3"
        if out_path.exists() and not args.overwrite:
            print(f"skipping: {out_path.name} already exists (use --overwrite to replace)")
            skipped += 1
            continue
        if join_pair(pt1, pt2, out_path, args.dry_run):
            success += 1
        else:
            failed += 1

    print(f"\nDone — joined: {success}, skipped: {skipped}, failed: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
