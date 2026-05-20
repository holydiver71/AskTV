"""
vectorise_metadata.py
---------------------
Fetches all metadata_chunks where embedding IS NULL from Supabase,
generates 512-dim embeddings via OpenAI text-embedding-3-small, and writes
them back.

Metadata chunks are short text documents derived from episode tracks and
sessions, built by upload_episodes.py and stored in the metadata_chunks table.

Safe to re-run: only rows with embedding IS NULL are processed.
Safe to interrupt: already-embedded rows are never re-submitted.

Usage:
  python scripts/vectorise_metadata.py [--batch 100] [--dry-run]

  --batch   Number of chunks per OpenAI request (default: 100, max: 2048)
  --dry-run Print how many chunks would be processed and estimated cost,
            then exit without calling OpenAI.

Logs to logs/vectorise_metadata.log
Pricing ref: text-embedding-3-small = $0.02 / 1M tokens (as of 2025)
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
EMBEDDING_MODEL     = "text-embedding-3-small"
EMBEDDING_DIMS      = 512
COST_PER_1M_TOKENS  = 0.02          # USD — update if pricing changes
AVG_TOKENS_PER_CHUNK = 40           # metadata docs are shorter than transcript chunks
PAGE_SIZE           = 1000          # rows per Supabase SELECT page

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_PATH = Path("logs/vectorise_metadata.log")
LOG_PATH.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fetch_unembedded(sb: Client) -> list[dict]:
    """
    Return all metadata_chunks where embedding IS NULL.

    Paginates in PAGE_SIZE chunks to avoid response-size limits.
    """
    rows: list[dict] = []
    offset = 0
    while True:
        result = (
            sb.table("metadata_chunks")
              .select("id, text, source_type")
              .is_("embedding", "null")
              .range(offset, offset + PAGE_SIZE - 1)
              .execute()
        )
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def embed_batch(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API for a batch of texts."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
        dimensions=EMBEDDING_DIMS,
    )
    # Response items are ordered to match input order
    return [item.embedding for item in response.data]


def update_embeddings(
    sb: Client, ids: list[str], embeddings: list[list[float]]
) -> None:
    """Write embeddings back to Supabase one row at a time."""
    for row_id, embedding in zip(ids, embeddings):
        sb.table("metadata_chunks").update(
            {"embedding": embedding}
        ).eq("id", row_id).execute()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(batch_size: int, dry_run: bool) -> None:
    load_dotenv()

    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_SERVICE_KEY")
    oai_key = os.environ.get("OPENAI_API_KEY")

    missing = [k for k, v in {
        "SUPABASE_URL": sb_url,
        "SUPABASE_SERVICE_KEY": sb_key,
        "OPENAI_API_KEY": oai_key,
    }.items() if not v]
    if missing:
        log.error("Missing env vars: %s", ", ".join(missing))
        sys.exit(1)

    sb: Client = create_client(sb_url, sb_key)  # type: ignore[arg-type]
    log.info("Fetching unembedded metadata chunks…")
    rows = fetch_unembedded(sb)

    if not rows:
        log.info("No unembedded metadata chunks found — nothing to do.")
        return

    total = len(rows)
    est_tokens = total * AVG_TOKENS_PER_CHUNK
    est_cost   = (est_tokens / 1_000_000) * COST_PER_1M_TOKENS
    log.info(
        "Found %d chunks to embed  |  est. tokens: ~%d  |  est. cost: ~$%.4f",
        total, est_tokens, est_cost,
    )

    if dry_run:
        log.info("--dry-run: exiting without calling OpenAI.")
        return

    oai = OpenAI(api_key=oai_key)
    processed = 0

    for start in range(0, total, batch_size):
        chunk = rows[start : start + batch_size]
        texts = [r["text"] for r in chunk]
        ids   = [r["id"]   for r in chunk]

        try:
            embeddings = embed_batch(oai, texts)
            update_embeddings(sb, ids, embeddings)
            processed += len(chunk)
            log.info(
                "Embedded %d/%d  (batch %d–%d)",
                processed, total, start + 1, start + len(chunk),
            )
        except Exception as exc:
            log.error("Failed on batch %d–%d: %s", start, start + len(chunk), exc)
            log.error("Script will stop here — re-run to resume from this point.")
            sys.exit(1)

    log.info("Done. %d metadata chunks embedded.", processed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate OpenAI embeddings for metadata_chunks"
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=100,
        help="Chunks per OpenAI request (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print stats and estimated cost without calling OpenAI",
    )
    args = parser.parse_args()
    main(args.batch, args.dry_run)
