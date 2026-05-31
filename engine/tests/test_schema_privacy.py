import sqlite3

from app.models.schema import FORBIDDEN_FINDING_COLUMNS, SCHEMA_SQL


def test_finding_table_has_no_raw_pii_columns():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(finding)")}
    forbidden_present = cols & FORBIDDEN_FINDING_COLUMNS
    assert not forbidden_present, f"Forbidden columns present: {forbidden_present}"
