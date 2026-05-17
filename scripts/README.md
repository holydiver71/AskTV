Extractor (scripts/extractor.py)
================================

This script extracts Friday Rock Show episode metadata from the fandom wiki
and writes one JSON file per episode into `data/episodes/<YEAR>/`.

Quick start

1. Put your exported `cookies.txt` (Netscape format) at the repository root.
2. Install dependencies (use your venv):

```bash
python -m pip install -r requirements.txt
```

3. Run the extractor (defaults to `YEAR=1980`):

```bash
python scripts/extractor.py
```

Configuration

- Edit `scripts/extractor.py` to change `YEAR` or `DELAY_SECONDS`.
- Output will be written to `data/episodes/<YEAR>/FRS YYYY-MM-DD.json`.

Notes

- The original external `FRSEpisodeDetailExtractor` repository has been
  consolidated into this repo. The `scripts/extractor.py` file is the
  canonical copy to use.
