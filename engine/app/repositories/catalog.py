"""Catalog repository — sole SQL access layer."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.schema import SCHEMA_SQL


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# init_db runs on nearly every API request; repeating executescript during a
# background scan holds schema locks and causes "database is locked" on progress
# writes. One init per resolved db path per process is enough.
_init_lock = threading.Lock()
_init_done: set[Path] = set()


@dataclass
class CatalogRepository:
    db_path: Path

    def connect(self) -> sqlite3.Connection:
        # 30s busy timeout + WAL so dashboard reads don't collide with a long scan's
        # writes ("database is locked"). WAL lets readers proceed during writes.
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
        except sqlite3.Error:
            pass
        return conn

    def init_db(self, seed_sql_path: Path | None = None) -> None:
        key = self.db_path.resolve()
        with _init_lock:
            if key in _init_done:
                return
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self.connect() as conn:
                conn.executescript(SCHEMA_SQL)
                self._migrate(conn)
                # Seed the classification enum only when empty. init_db runs on every
                # request, and the seed file is DELETE+INSERT; re-running it concurrently
                # (e.g. dashboard polling during a background scan) races and trips a
                # UNIQUE constraint. Seeding once keeps it idempotent and race-free.
                if seed_sql_path and seed_sql_path.is_file():
                    row = conn.execute("SELECT COUNT(*) AS c FROM classification_enum").fetchone()
                    if not row or row["c"] == 0:
                        conn.executescript(seed_sql_path.read_text(encoding="utf-8"))
                conn.commit()
            _init_done.add(key)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Additive column migrations for pre-existing catalogs (idempotent)."""
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(scan_run)")}
        additions = {
            "total_bytes": "INTEGER NOT NULL DEFAULT 0",
            "duration_ms": "INTEGER",
            "type_breakdown": "TEXT",
        }
        for column, decl in additions.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE scan_run ADD COLUMN {column} {decl}")

    def reset_catalog(self, seed_sql_path: Path | None = None) -> None:
        """Clear all scan/findings data and re-seed classification enum."""
        key = self.db_path.resolve()
        with self.connect() as conn:
            conn.executescript(
                """
                DELETE FROM finding;
                DELETE FROM audit_log;
                DELETE FROM file_ownership;
                DELETE FROM scan_catalog;
                DELETE FROM scan_run;
                DELETE FROM source_delta_state;
                DELETE FROM owner_edge;
                DELETE FROM classification_enum;
                """
            )
            if seed_sql_path and seed_sql_path.is_file():
                conn.executescript(seed_sql_path.read_text(encoding="utf-8"))
            conn.commit()
        with _init_lock:
            _init_done.add(key)

    def upsert_catalog(
        self,
        conn: sqlite3.Connection,
        *,
        file_id: str,
        source_id: str,
        path: str,
        content_hash: str | None,
        size: int | None,
        mtime: float | None,
        ruleset_version: str,
        scan_status: str,
        model_version: str | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO scan_catalog (
                file_id, source_id, path, content_hash, size, mtime,
                last_scanned_ts, ruleset_version, model_version, scan_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_id) DO UPDATE SET
                content_hash=excluded.content_hash,
                size=excluded.size,
                mtime=excluded.mtime,
                last_scanned_ts=excluded.last_scanned_ts,
                ruleset_version=excluded.ruleset_version,
                model_version=excluded.model_version,
                scan_status=excluded.scan_status
            """,
            (
                file_id,
                source_id,
                path,
                content_hash,
                size,
                mtime,
                _utc_now(),
                ruleset_version,
                model_version,
                scan_status,
            ),
        )

    def insert_finding(
        self,
        conn: sqlite3.Connection,
        *,
        file_id: str,
        classification_code: str,
        location: dict[str, Any],
        masked_snippet: str,
        risk_score: float,
        confidence_score: float,
        tier: int = 1,
        detector_version: str | None = None,
        model_version: str | None = None,
        prompt_hash: str | None = None,
        owner_user_id: str | None = None,
        resolution_method: str | None = None,
    ) -> int:
        cur = conn.execute(
            """
            INSERT INTO finding (
                file_id, classification_code, location_json, masked_snippet,
                risk_score, confidence_score, tier, detector_version,
                model_version, prompt_hash, owner_user_id, resolution_method,
                created_ts, resolution_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
            """,
            (
                file_id,
                classification_code,
                json.dumps(location, sort_keys=True),
                masked_snippet,
                risk_score,
                confidence_score,
                tier,
                detector_version,
                model_version,
                prompt_hash,
                owner_user_id,
                resolution_method,
                _utc_now(),
            ),
        )
        return int(cur.lastrowid)

    def append_audit(
        self,
        conn: sqlite3.Connection,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: str | None = None,
        justification: str | None = None,
        detector_version: str | None = None,
        model_version: str | None = None,
        prompt_hash: str | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO audit_log (
                id, entity_type, entity_id, action, actor, justification,
                detector_version, model_version, prompt_hash, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                entity_type,
                entity_id,
                action,
                actor,
                justification,
                detector_version,
                model_version,
                prompt_hash,
                _utc_now(),
            ),
        )

    def set_file_ownership(
        self,
        conn: sqlite3.Connection,
        *,
        file_id: str,
        owner_user_id: str | None,
        resolution_method: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO file_ownership (file_id, owner_user_id, resolution_method)
            VALUES (?, ?, ?)
            ON CONFLICT(file_id) DO UPDATE SET
                owner_user_id=excluded.owner_user_id,
                resolution_method=excluded.resolution_method
            """,
            (file_id, owner_user_id, resolution_method),
        )

    def list_findings(self, conn: sqlite3.Connection, file_id: str | None = None) -> list[sqlite3.Row]:
        if file_id:
            return list(
                conn.execute(
                    "SELECT * FROM finding WHERE file_id = ? ORDER BY id",
                    (file_id,),
                )
            )
        return list(conn.execute("SELECT * FROM finding ORDER BY file_id, id"))

    def list_open_findings_for_owner(
        self, conn: sqlite3.Connection, owner_user_id: str
    ) -> list[sqlite3.Row]:
        return list(
            conn.execute(
                """
                SELECT f.*, c.path AS file_path
                FROM finding f
                JOIN scan_catalog c ON c.file_id = f.file_id
                WHERE f.owner_user_id = ? AND f.resolution_status = 'open'
                ORDER BY f.risk_score DESC, f.id ASC
                """,
                (owner_user_id,),
            )
        )

    def get_finding(self, conn: sqlite3.Connection, finding_id: int) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT f.*, c.path AS file_path
            FROM finding f
            JOIN scan_catalog c ON c.file_id = f.file_id
            WHERE f.id = ?
            """,
            (finding_id,),
        ).fetchone()

    def update_finding_resolution(
        self,
        conn: sqlite3.Connection,
        finding_id: int,
        *,
        resolution_status: str,
        actor: str,
        action: str,
        justification: str | None = None,
    ) -> sqlite3.Row | None:
        row = self.get_finding(conn, finding_id)
        if row is None:
            return None
        conn.execute(
            "UPDATE finding SET resolution_status = ? WHERE id = ?",
            (resolution_status, finding_id),
        )
        self.append_audit(
            conn,
            entity_type="finding",
            entity_id=str(finding_id),
            action=action,
            actor=actor,
            justification=justification,
            detector_version=row["detector_version"],
            model_version=row["model_version"],
            prompt_hash=row["prompt_hash"],
        )
        return self.get_finding(conn, finding_id)

    def count_catalog(self, conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT COUNT(*) AS c FROM scan_catalog").fetchone()
        return int(row["c"])

    def get_catalog_entry(self, conn: sqlite3.Connection, file_id: str) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM scan_catalog WHERE file_id = ?",
            (file_id,),
        ).fetchone()

    def list_catalog_for_scope(self, conn: sqlite3.Connection, scope_id: str) -> list[sqlite3.Row]:
        return list(
            conn.execute(
                "SELECT * FROM scan_catalog WHERE source_id = ?",
                (scope_id,),
            )
        )

    def delete_catalog(self, conn: sqlite3.Connection, file_id: str) -> None:
        conn.execute("DELETE FROM finding WHERE file_id = ?", (file_id,))
        conn.execute("DELETE FROM file_ownership WHERE file_id = ?", (file_id,))
        conn.execute("DELETE FROM scan_catalog WHERE file_id = ?", (file_id,))

    def update_finding_tier2(
        self,
        conn: sqlite3.Connection,
        finding_id: int,
        *,
        confidence_score: float,
        tier: int,
        model_version: str,
        prompt_hash: str,
    ) -> None:
        row = conn.execute(
            "SELECT detector_version FROM finding WHERE id = ?",
            (finding_id,),
        ).fetchone()
        conn.execute(
            """
            UPDATE finding
            SET confidence_score = ?, tier = ?, model_version = ?, prompt_hash = ?
            WHERE id = ?
            """,
            (confidence_score, tier, model_version, prompt_hash, finding_id),
        )
        self.append_audit(
            conn,
            entity_type="finding",
            entity_id=str(finding_id),
            action="tier2_verdict",
            detector_version=row["detector_version"] if row else None,
            model_version=model_version,
            prompt_hash=prompt_hash,
        )

    def insert_scan_run(
        self,
        conn: sqlite3.Connection,
        *,
        scan_id: str,
        scope_id: str | None,
        mode: str,
        status: str,
        files_total: int,
        ruleset_version: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO scan_run (
                scan_id, scope_id, mode, status, files_total, files_scanned,
                findings_count, tier2_applied, started_ts, completed_ts, ruleset_version
            ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?, NULL, ?)
            """,
            (scan_id, scope_id, mode, status, files_total, _utc_now(), ruleset_version),
        )

    def update_scan_run(
        self,
        conn: sqlite3.Connection,
        scan_id: str,
        *,
        status: str,
        files_scanned: int,
        findings_count: int,
        tier2_applied: int = 0,
        total_bytes: int | None = None,
        duration_ms: int | None = None,
        type_breakdown: str | None = None,
    ) -> None:
        conn.execute(
            """
            UPDATE scan_run
            SET status = ?, files_scanned = ?, findings_count = ?,
                tier2_applied = ?, completed_ts = ?,
                total_bytes = COALESCE(?, total_bytes),
                duration_ms = COALESCE(?, duration_ms),
                type_breakdown = COALESCE(?, type_breakdown)
            WHERE scan_id = ?
            """,
            (
                status,
                files_scanned,
                findings_count,
                tier2_applied,
                _utc_now(),
                total_bytes,
                duration_ms,
                type_breakdown,
                scan_id,
            ),
        )

    def get_scan_run(self, conn: sqlite3.Connection, scan_id: str) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM scan_run WHERE scan_id = ?",
            (scan_id,),
        ).fetchone()

    def get_delta_token(self, conn: sqlite3.Connection, scope_id: str) -> str | None:
        row = conn.execute(
            "SELECT delta_token FROM source_delta_state WHERE scope_id = ?",
            (scope_id,),
        ).fetchone()
        return row["delta_token"] if row else None

    def set_delta_token(self, conn: sqlite3.Connection, scope_id: str, token: str) -> None:
        conn.execute(
            """
            INSERT INTO source_delta_state (scope_id, delta_token, updated_ts)
            VALUES (?, ?, ?)
            ON CONFLICT(scope_id) DO UPDATE SET
                delta_token = excluded.delta_token,
                updated_ts = excluded.updated_ts
            """,
            (scope_id, token, _utc_now()),
        )
