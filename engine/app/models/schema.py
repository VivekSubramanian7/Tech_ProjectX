"""SQLite DDL — privacy-by-design: finding has no raw PII column."""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS classification_enum (
    machine_code TEXT PRIMARY KEY,
    display_label TEXT NOT NULL,
    modality TEXT NOT NULL,
    mvp_flag INTEGER NOT NULL,
    risk_weight TEXT NOT NULL,
    gdpr_focus TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scan_catalog (
    file_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    path TEXT NOT NULL,
    content_hash TEXT,
    size INTEGER,
    mtime REAL,
    last_scanned_ts TEXT,
    ruleset_version TEXT,
    model_version TEXT,
    scan_status TEXT
);

CREATE TABLE IF NOT EXISTS finding (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL REFERENCES scan_catalog(file_id),
    classification_code TEXT NOT NULL REFERENCES classification_enum(machine_code),
    location_json TEXT NOT NULL,
    masked_snippet TEXT NOT NULL,
    risk_score REAL NOT NULL,
    confidence_score REAL NOT NULL,
    tier INTEGER NOT NULL DEFAULT 1,
    detector_version TEXT,
    model_version TEXT,
    prompt_hash TEXT,
    owner_user_id TEXT,
    resolution_method TEXT,
    created_ts TEXT NOT NULL,
    resolution_status TEXT NOT NULL DEFAULT 'open',
    FOREIGN KEY (file_id) REFERENCES scan_catalog(file_id)
);

CREATE TABLE IF NOT EXISTS owner_edge (
    user_id TEXT PRIMARY KEY,
    manager_id TEXT,
    role TEXT,
    delegate_id TEXT
);

CREATE TABLE IF NOT EXISTS file_ownership (
    file_id TEXT PRIMARY KEY,
    owner_user_id TEXT,
    resolution_method TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT,
    justification TEXT,
    detector_version TEXT,
    model_version TEXT,
    prompt_hash TEXT,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scan_run (
    scan_id TEXT PRIMARY KEY,
    scope_id TEXT,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    files_total INTEGER NOT NULL DEFAULT 0,
    files_scanned INTEGER NOT NULL DEFAULT 0,
    findings_count INTEGER NOT NULL DEFAULT 0,
    tier2_applied INTEGER NOT NULL DEFAULT 0,
    started_ts TEXT NOT NULL,
    completed_ts TEXT,
    ruleset_version TEXT
);

CREATE TABLE IF NOT EXISTS source_delta_state (
    scope_id TEXT PRIMARY KEY,
    delta_token TEXT NOT NULL,
    updated_ts TEXT NOT NULL
);
"""

# Column names that must never exist on finding (raw PII storage).
FORBIDDEN_FINDING_COLUMNS = frozenset(
    {
        "raw_value",
        "raw_text",
        "pii_value",
        "snippet_plain",
        "value",
        "plaintext",
        "original_text",
    }
)
