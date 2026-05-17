#!/usr/bin/env python3
"""Validate required .env entries for Supabase/OpenAI before running uploads/vectorisation.
Usage: python3 scripts/validate_env.py
Exits with code 0 when all checks pass, 1 otherwise.
"""
from dotenv import load_dotenv
import os
import sys

load_dotenv()

checks = [
    ("SUPABASE_URL", "Supabase project URL (e.g. https://<project>.supabase.co)"),
    ("SUPABASE_SERVICE_KEY", "Supabase service_role key (secret)"),
    ("SUPABASE_ANON_KEY", "Supabase anon/public key (for frontend)"),
    ("OPENAI_API_KEY", "OpenAI API key (server-side only)")
]

placeholders = set(["your-project-ref.supabase.co", "your-anon-public-key", "your-service-role-key", "sk-..."])

missing = []
for k,desc in checks:
    v = os.getenv(k, "").strip()
    if not v or any(p in v for p in placeholders):
        missing.append((k, desc, v))

if missing:
    print("ERROR: Required environment variables missing or still placeholders:\n")
    for k,desc,val in missing:
        example = "(set in .env or environment)"
        print(f"- {k}: {desc} {example}")
    print("\nPlease edit .env and add the real values. The .env file is already in .gitignore.")
    sys.exit(1)

print("All required environment variables appear to be set.")
sys.exit(0)
