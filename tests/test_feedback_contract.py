"""The feedback box's length cap is declared twice. They must agree.

1. `sql/008_feedback.sql`  — the CHECK the database enforces.
2. `web/lib/model.ts`      — the `maxLength` the textarea enforces.

If the browser's cap were the looser of the two, a note written right up to it
would be refused on arrival and the writer would be told it did not save, with
nothing in the interface explaining why. Read as text: no database, no Node.
"""
from __future__ import annotations

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parent.parent
MIGRATION = REPO / "sql" / "008_feedback.sql"
MODEL_TS = REPO / "web" / "lib" / "model.ts"


def sql_bound() -> int:
    found = re.search(
        r"length\(btrim\(message\)\)\s+BETWEEN\s+1\s+AND\s+(\d+)",
        MIGRATION.read_text(encoding="utf-8"),
    )
    assert found, "008_feedback.sql no longer bounds the message length"
    return int(found.group(1))


def ts_bound() -> int:
    found = re.search(r"MAX_FEEDBACK\s*=\s*(\d+)", MODEL_TS.read_text(encoding="utf-8"))
    assert found, "lib/model.ts no longer declares MAX_FEEDBACK"
    return int(found.group(1))


def test_the_two_length_caps_agree():
    assert ts_bound() == sql_bound()


def test_the_migration_is_re_runnable():
    # init_db.py applies every sql/ file on each run, so 008 has to tolerate
    # being applied to a database that already has the table.
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS feedback" in sql
    assert "CREATE INDEX IF NOT EXISTS" in sql
