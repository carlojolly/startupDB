"""Shared database helpers.

Every script imports connect() from here so there is exactly one place that
knows how we reach Postgres.
"""
from __future__ import annotations

import os
import pathlib
import sys

import psycopg
from dotenv import load_dotenv

if sys.version_info < (3, 11):
    # datetime.UTC and the asyncio TimeoutError alias both arrived in 3.11;
    # on 3.10 the render pass would crash instead of recording a timeout.
    sys.exit(f"ERROR: Python 3.11 or newer is required (found {sys.version.split()[0]}).")

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SQL_DIR = REPO_ROOT / "sql"
DATA_DIR = REPO_ROOT / "data" / "raw"


def get_database_url(override: str | None = None) -> str:
    """Read DATABASE_URL from the environment or the .env file."""
    if override:
        return override

    load_dotenv(REPO_ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit(
            "ERROR: DATABASE_URL is not set.\n"
            "  1. Copy the template:  cp .env.example .env\n"
            "  2. Paste your Supabase/Neon connection string into .env\n"
            "See the README section 'Getting a database' for where to find it."
        )
    return url


def connect(override: str | None = None) -> psycopg.Connection:
    """Open a connection. Caller is responsible for commit/rollback."""
    url = get_database_url(override)
    try:
        return psycopg.connect(url)
    except psycopg.OperationalError as exc:
        sys.exit(
            f"ERROR: could not connect to the database.\n  {exc}\n"
            "Check that DATABASE_URL in .env is correct and that your IP is "
            "allowed by the provider."
        )
