from __future__ import annotations

import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import timezone
from pathlib import Path
from typing import Any, Iterator

from .auth_utils import hash_password
from .auth_utils import utcnow
from .config import settings


_ALLOWED_JOURNAL_MODES = {"DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"}
_ALLOWED_SYNCHRONOUS = {"OFF", "NORMAL", "FULL", "EXTRA"}
_VACUUM_MIN_PAGE_COUNT = 200
_VACUUM_MIN_FREE_RATIO = 0.20
_SEED_ADMIN_BOOTSTRAP_FILENAME = "bootstrap_admin_credentials.json"

_data_integrity_status: dict[str, object] = {
    "checked_at": "",
    "ok": True,
    "message": "not checked",
    "trade_opportunity_unique_index": False,
    "has_duplicate_trade_opportunities": False,
    "duplicate_trade_opportunity_count": 0,
    "duplicate_trade_opportunity_ids": [],
}

_batch_write_status: dict[str, object] = {
    "last_batch_at": "",
    "last_batch_size": 0,
    "last_batch_duration_ms": 0,
    "last_batch_error": "",
}

_DIAGNOSTIC_QUERY_PLANS: dict[str, str] = {
    "get_open_listings": (
        "EXPLAIN QUERY PLAN "
        "SELECT * FROM listings_raw "
        "WHERE status = 'open' AND normalization_blocked = 0 "
        "ORDER BY listed_at DESC LIMIT 50"
    ),
    "list_opportunities": (
        "EXPLAIN QUERY PLAN "
        "SELECT o.*, l.title, l.list_price, v.expected_sale_price, v.suggested_list_price "
        "FROM opportunities o "
        "JOIN listings_raw l ON l.id = o.listing_row_id "
        "JOIN valuation_records v ON v.id = o.valuation_id "
        "WHERE o.status = 'pending_review' "
        "ORDER BY o.score DESC LIMIT 100"
    ),
    "list_trades": (
        "EXPLAIN QUERY PLAN "
        "SELECT t.*, o.listing_row_id, l.title, l.list_price "
        "FROM trades t "
        "JOIN opportunities o ON o.id = t.opportunity_id "
        "JOIN listings_raw l ON l.id = o.listing_row_id "
        "WHERE t.status = 'approved_for_buy' "
        "ORDER BY t.updated_at DESC LIMIT 100"
    ),
    "latest_valuation": (
        "EXPLAIN QUERY PLAN "
        "SELECT * FROM valuation_records WHERE listing_row_id = 1 ORDER BY id DESC LIMIT 1"
    ),
    "latest_execution_log": (
        "EXPLAIN QUERY PLAN "
        "SELECT * FROM execution_logs WHERE trade_id = 1 AND action = 'buy' ORDER BY id DESC LIMIT 1"
    ),
}


def _desired_journal_mode() -> str:
    value = str(settings.sqlite_journal_mode or "WAL").strip().upper()
    return value if value in _ALLOWED_JOURNAL_MODES else "WAL"


def _desired_synchronous() -> str:
    value = str(settings.sqlite_synchronous or "NORMAL").strip().upper()
    return value if value in _ALLOWED_SYNCHRONOUS else "NORMAL"


def _normalize_synchronous_value(raw: Any) -> str:
    mapping = {0: "OFF", 1: "NORMAL", 2: "FULL", 3: "EXTRA"}
    try:
        key = int(raw)
    except (TypeError, ValueError):
        text = str(raw or "").strip().upper()
        return text or "UNKNOWN"
    return mapping.get(key, str(key))


def _sqlite_uri(path: Path, *, readonly: bool) -> str:
    suffix = "?mode=ro" if readonly else ""
    return f"file:{path.as_posix()}{suffix}"


def _apply_connection_pragmas(conn: sqlite3.Connection, *, readonly: bool) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {max(0, int(settings.sqlite_busy_timeout_ms))}")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA synchronous = {_desired_synchronous()}")
    if readonly:
        return
    conn.execute(f"PRAGMA journal_mode = {_desired_journal_mode()}").fetchone()


def _connect(*, readonly: bool = False) -> sqlite3.Connection:
    settings.ensure_paths()
    db_path = Path(settings.sqlite_path).expanduser()
    if readonly:
        conn = sqlite3.connect(_sqlite_uri(db_path, readonly=True), uri=True, check_same_thread=False)
    else:
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
    _apply_connection_pragmas(conn, readonly=readonly)
    return conn


def _ensure_table_columns(
    conn: sqlite3.Connection,
    table: str,
    columns: dict[str, str],
) -> None:
    existing = {
        str(row["name"] or "")
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for column_name, ddl in columns.items():
        if column_name in existing:
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_readonly_conn() -> Iterator[sqlite3.Connection]:
    conn = _connect(readonly=True)
    try:
        yield conn
    finally:
        conn.close()


def _trade_unique_index_exists(conn: sqlite3.Connection) -> bool:
    rows = conn.execute("PRAGMA index_list('trades')").fetchall()
    for row in rows:
        if str(row["name"]) == "ux_trades_opportunity_id":
            return True
    return False


def _snapshot_data_integrity(conn: sqlite3.Connection) -> dict[str, object]:
    duplicate_rows = conn.execute(
        """
        SELECT opportunity_id, COUNT(*) AS trade_count
        FROM trades
        GROUP BY opportunity_id
        HAVING COUNT(*) > 1
        ORDER BY trade_count DESC, opportunity_id DESC
        LIMIT 20
        """
    ).fetchall()
    duplicate_items = [
        {
            "opportunity_id": int(row["opportunity_id"]),
            "trade_count": int(row["trade_count"]),
        }
        for row in duplicate_rows
    ]
    return {
        "checked_at": utcnow().astimezone(timezone.utc).isoformat(),
        "trade_opportunity_unique_index": _trade_unique_index_exists(conn),
        "has_duplicate_trade_opportunities": bool(duplicate_items),
        "duplicate_trade_opportunity_count": len(duplicate_items),
        "duplicate_trade_opportunity_ids": duplicate_items,
    }


def _set_data_integrity_status(payload: dict[str, object]) -> None:
    global _data_integrity_status
    _data_integrity_status = {**payload}


def get_data_integrity_status() -> dict[str, object]:
    return {**_data_integrity_status}


def record_batch_write_status(*, batch_size: int, duration_ms: int, error: str = "") -> None:
    global _batch_write_status
    _batch_write_status = {
        "last_batch_at": utcnow().astimezone(timezone.utc).isoformat(),
        "last_batch_size": max(0, int(batch_size)),
        "last_batch_duration_ms": max(0, int(duration_ms)),
        "last_batch_error": str(error or ""),
    }


def get_batch_write_status() -> dict[str, object]:
    return {**_batch_write_status}


def _file_size_or_zero(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except FileNotFoundError:
        return 0


def get_seed_admin_bootstrap_path() -> Path:
    db_path = Path(settings.sqlite_path).expanduser()
    return db_path.parent / _SEED_ADMIN_BOOTSTRAP_FILENAME


def _write_seed_admin_bootstrap(username: str, password: str) -> Path:
    bootstrap_path = get_seed_admin_bootstrap_path()
    bootstrap_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "username": username,
        "password": password,
        "created_at": utcnow().astimezone(timezone.utc).isoformat(),
    }
    bootstrap_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return bootstrap_path


def _resolve_seed_admin_password(username: str) -> str:
    configured = str(settings.ui_auth_password or "").strip()
    if configured:
        return configured

    bootstrap_path = get_seed_admin_bootstrap_path()
    try:
        payload = json.loads(bootstrap_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        payload = {}
    if isinstance(payload, dict):
        existing_username = str(payload.get("username") or "").strip()
        existing_password = str(payload.get("password") or "").strip()
        if existing_username == username and existing_password:
            return existing_password

    generated = secrets.token_urlsafe(18)
    _write_seed_admin_bootstrap(username, generated)
    return generated


def _database_unavailable_payload(
    db_path: Path,
    *,
    reason: str,
    error: str = "",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "sqlite_path": str(db_path),
        "available": False,
        "degraded_reasons": [reason],
        "batch_writes": get_batch_write_status(),
    }
    if error:
        payload["error"] = error
    return payload


def _collect_table_diagnostics(conn: sqlite3.Connection) -> dict[str, dict[str, object]]:
    tables: dict[str, dict[str, object]] = {}
    table_rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    for table_row in table_rows:
        name = str(table_row["name"])
        count = int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
        index_rows = conn.execute(f"PRAGMA index_list('{name}')").fetchall()
        indexes: list[dict[str, object]] = []
        for index_row in index_rows:
            index_name = str(index_row["name"])
            definition_row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
                (index_name,),
            ).fetchone()
            columns = [
                str(info_row["name"])
                for info_row in conn.execute(f"PRAGMA index_info('{index_name}')").fetchall()
            ]
            indexes.append(
                {
                    "name": index_name,
                    "unique": bool(index_row["unique"]),
                    "origin": str(index_row["origin"]),
                    "partial": bool(index_row["partial"]),
                    "columns": columns,
                    "definition": str(definition_row["sql"] or ""),
                }
            )
        tables[name] = {"rows": count, "indexes": indexes}
    return tables


def _collect_query_plans(conn: sqlite3.Connection) -> dict[str, list[tuple[Any, ...]]]:
    return {
        name: [tuple(row) for row in conn.execute(query).fetchall()]
        for name, query in _DIAGNOSTIC_QUERY_PLANS.items()
    }


def _collect_runtime_snapshot(conn: sqlite3.Connection, db_path: Path) -> dict[str, object]:
    journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).upper()
    synchronous = _normalize_synchronous_value(conn.execute("PRAGMA synchronous").fetchone()[0])
    busy_timeout_ms = int(conn.execute("PRAGMA busy_timeout").fetchone()[0])
    foreign_keys = bool(conn.execute("PRAGMA foreign_keys").fetchone()[0])
    page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
    page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
    freelist_count = int(conn.execute("PRAGMA freelist_count").fetchone()[0])
    sqlite_version = str(conn.execute("SELECT sqlite_version()").fetchone()[0])
    free_ratio = (freelist_count / float(page_count)) if page_count else 0.0
    vacuum_recommended = (
        page_count >= _VACUUM_MIN_PAGE_COUNT and free_ratio >= _VACUUM_MIN_FREE_RATIO
    )
    degraded_reasons: list[str] = []
    if journal_mode != _desired_journal_mode():
        degraded_reasons.append(f"journal_mode:{journal_mode.lower()}")
    if synchronous != _desired_synchronous():
        degraded_reasons.append(f"synchronous:{synchronous.lower()}")
    if not foreign_keys:
        degraded_reasons.append("foreign_keys_disabled")

    return {
        "sqlite_version": sqlite_version,
        "runtime": {
            "journal_mode": journal_mode,
            "synchronous": synchronous,
            "busy_timeout_ms": busy_timeout_ms,
            "foreign_keys": foreign_keys,
        },
        "files": {
            "db_bytes": _file_size_or_zero(db_path),
            "wal_bytes": _file_size_or_zero(Path(f"{db_path}-wal")),
            "shm_bytes": _file_size_or_zero(Path(f"{db_path}-shm")),
        },
        "pages": {
            "page_count": page_count,
            "page_size": page_size,
            "freelist_count": freelist_count,
            "freelist_ratio": round(free_ratio, 4),
        },
        "vacuum_recommended": vacuum_recommended,
        "degraded_reasons": degraded_reasons,
    }


def collect_database_diagnostics(*, include_query_plans: bool = True) -> dict[str, object]:
    db_path = Path(settings.sqlite_path).expanduser()
    if not db_path.exists():
        return _database_unavailable_payload(
            db_path,
            reason="database_missing",
            error="database file does not exist",
        )

    try:
        with get_readonly_conn() as conn:
            runtime_snapshot = _collect_runtime_snapshot(conn, db_path)
            payload: dict[str, object] = {
                "sqlite_path": str(db_path),
                "available": True,
                **runtime_snapshot,
                "batch_writes": get_batch_write_status(),
                "duplicate_trade_opportunity_rows": _snapshot_data_integrity(conn)[
                    "duplicate_trade_opportunity_ids"
                ],
                "tables": _collect_table_diagnostics(conn),
            }
            if include_query_plans:
                payload["query_plans"] = _collect_query_plans(conn)
            return payload
    except sqlite3.Error as exc:
        return _database_unavailable_payload(
            db_path,
            reason="database_open_failed",
            error=str(exc),
        )


def get_database_health_snapshot() -> dict[str, object]:
    db_path = Path(settings.sqlite_path).expanduser()
    if not db_path.exists():
        return _database_unavailable_payload(
            db_path,
            reason="database_missing",
            error="database file does not exist",
        )

    try:
        with get_readonly_conn() as conn:
            runtime_snapshot = _collect_runtime_snapshot(conn, db_path)
    except sqlite3.Error as exc:
        return _database_unavailable_payload(
            db_path,
            reason="database_open_failed",
            error=str(exc),
        )

    runtime = dict(runtime_snapshot.get("runtime") or {})
    files = dict(runtime_snapshot.get("files") or {})
    pages = dict(runtime_snapshot.get("pages") or {})
    return {
        "sqlite_path": str(db_path),
        "available": True,
        "journal_mode": runtime.get("journal_mode", ""),
        "synchronous": runtime.get("synchronous", ""),
        "busy_timeout_ms": runtime.get("busy_timeout_ms", 0),
        "foreign_keys": runtime.get("foreign_keys", False),
        "db_bytes": files.get("db_bytes", 0),
        "wal_bytes": files.get("wal_bytes", 0),
        "page_count": pages.get("page_count", 0),
        "freelist_count": pages.get("freelist_count", 0),
        "freelist_ratio": pages.get("freelist_ratio", 0.0),
        "vacuum_recommended": runtime_snapshot.get("vacuum_recommended", False),
        "degraded_reasons": runtime_snapshot.get("degraded_reasons", []),
        "batch_writes": get_batch_write_status(),
    }


def _ensure_trade_uniqueness(conn: sqlite3.Connection) -> dict[str, object]:
    snapshot = _snapshot_data_integrity(conn)
    if snapshot["has_duplicate_trade_opportunities"]:
        snapshot["ok"] = False
        snapshot["message"] = "duplicate trades detected; skipped unique index creation"
        _set_data_integrity_status(snapshot)
        return snapshot

    if not snapshot["trade_opportunity_unique_index"]:
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_trades_opportunity_id
            ON trades(opportunity_id)
            """
        )
        snapshot = _snapshot_data_integrity(conn)

    snapshot["ok"] = bool(snapshot["trade_opportunity_unique_index"])
    snapshot["message"] = (
        "trade opportunity unique index is ready"
        if snapshot["ok"]
        else "trade opportunity unique index creation failed"
    )
    _set_data_integrity_status(snapshot)
    return snapshot


def _ensure_seed_admin(conn: sqlite3.Connection) -> None:
    username = settings.ui_auth_username.strip() or "operator"
    existing = conn.execute(
        """
        SELECT id
        FROM users
        WHERE lower(username) = lower(?)
        LIMIT 1
        """,
        (username,),
    ).fetchone()

    if existing:
        return

    nickname = settings.ui_auth_nickname.strip() or username
    password_hash = hash_password(_resolve_seed_admin_password(username))
    now = utcnow().isoformat()
    conn.execute(
        """
        INSERT INTO users (
            username,
            email,
            password_hash,
            nickname,
            role,
            is_active,
            is_seeded_admin,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, 'admin', 1, 1, ?, ?)
        """,
        (username, f"{username}@local", password_hash, nickname, now, now),
    )


def init_db() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS sales_raw (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        item_id TEXT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        sold_price REAL NOT NULL,
        sold_at TEXT NOT NULL,
        normalized_title TEXT NOT NULL DEFAULT '',
        normalized_key TEXT NOT NULL DEFAULT '',
        item_type TEXT NOT NULL DEFAULT 'unknown',
        noise_flags_json TEXT NOT NULL DEFAULT '[]',
        normalization_confidence REAL NOT NULL DEFAULT 0.0,
        normalization_blocked INTEGER NOT NULL DEFAULT 0,
        normalization_reason TEXT NOT NULL DEFAULT '',
        normalization_version TEXT NOT NULL DEFAULT '',
        raw_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS listings_raw (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        listing_id TEXT,
        seller_id TEXT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        list_price REAL NOT NULL,
        listed_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        normalized_title TEXT NOT NULL DEFAULT '',
        normalized_key TEXT NOT NULL DEFAULT '',
        item_type TEXT NOT NULL DEFAULT 'unknown',
        noise_flags_json TEXT NOT NULL DEFAULT '[]',
        normalization_confidence REAL NOT NULL DEFAULT 0.0,
        normalization_blocked INTEGER NOT NULL DEFAULT 0,
        normalization_reason TEXT NOT NULL DEFAULT '',
        normalization_version TEXT NOT NULL DEFAULT '',
        raw_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS item_features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref_type TEXT NOT NULL,
        ref_id INTEGER NOT NULL,
        card_name TEXT NOT NULL,
        rarity TEXT NOT NULL DEFAULT 'unknown',
        edition TEXT NOT NULL DEFAULT 'unknown',
        card_condition TEXT NOT NULL DEFAULT 'unknown',
        extras_json TEXT NOT NULL DEFAULT '{}',
        confidence REAL NOT NULL DEFAULT 0.5,
        extracted_by TEXT NOT NULL,
        extracted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ref_type, ref_id)
    );

    CREATE TABLE IF NOT EXISTS valuation_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_row_id INTEGER NOT NULL,
        expected_sale_price REAL NOT NULL,
        buy_limit REAL NOT NULL,
        suggested_list_price REAL NOT NULL,
        ci_low REAL NOT NULL,
        ci_high REAL NOT NULL,
        model_confidence REAL NOT NULL,
        comparables_count INTEGER NOT NULL,
        reasoning TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(listing_row_id) REFERENCES listings_raw(id)
    );

    CREATE TABLE IF NOT EXISTS opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_row_id INTEGER NOT NULL UNIQUE,
        valuation_id INTEGER NOT NULL,
        expected_profit REAL NOT NULL,
        roi REAL NOT NULL,
        score REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending_review',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TEXT,
        review_note TEXT DEFAULT '',
        FOREIGN KEY(listing_row_id) REFERENCES listings_raw(id),
        FOREIGN KEY(valuation_id) REFERENCES valuation_records(id)
    );

    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        opportunity_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'approved_for_buy',
        approved_buy_price REAL NOT NULL,
        target_sell_price REAL NOT NULL,
        approved_by TEXT NOT NULL,
        listing_url TEXT DEFAULT '',
        sold_price REAL,
        note TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
    );

    CREATE TABLE IF NOT EXISTS forward_validation_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        target_sample_size INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        auto_enroll INTEGER NOT NULL DEFAULT 1,
        note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        closed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS forward_validation_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        trade_id INTEGER NOT NULL UNIQUE,
        enrolled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        enrollment_note TEXT NOT NULL DEFAULT '',
        FOREIGN KEY(batch_id) REFERENCES forward_validation_batches(id) ON DELETE CASCADE,
        FOREIGN KEY(trade_id) REFERENCES trades(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS execution_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        provider TEXT NOT NULL,
        dry_run INTEGER NOT NULL DEFAULT 1,
        request_json TEXT NOT NULL DEFAULT '{}',
        response_json TEXT NOT NULL DEFAULT '{}',
        success INTEGER NOT NULL DEFAULT 0,
        error TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(trade_id) REFERENCES trades(id)
    );

    CREATE TABLE IF NOT EXISTS autotrade_tuning_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL DEFAULT '',
        applied_by TEXT NOT NULL DEFAULT '',
        note TEXT NOT NULL DEFAULT '',
        previous_config_json TEXT NOT NULL DEFAULT '{}',
        next_config_json TEXT NOT NULL DEFAULT '{}',
        rollback_of_event_id INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(rollback_of_event_id) REFERENCES autotrade_tuning_events(id)
    );

    CREATE TABLE IF NOT EXISTS autotrade_tuning_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        decision_type TEXT NOT NULL DEFAULT '',
        trigger_source TEXT NOT NULL DEFAULT '',
        actor TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        details_json TEXT NOT NULL DEFAULT '{}',
        related_event_id INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(related_event_id) REFERENCES autotrade_tuning_events(id)
    );

    CREATE TABLE IF NOT EXISTS validation_baseline_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bucket_type TEXT NOT NULL DEFAULT '',
        bucket_key TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT '',
        ready INTEGER NOT NULL DEFAULT 0,
        ready_for_tune INTEGER NOT NULL DEFAULT 0,
        ready_for_scale INTEGER NOT NULL DEFAULT 0,
        direction TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        blocking_codes_json TEXT NOT NULL DEFAULT '[]',
        snapshot_json TEXT NOT NULL DEFAULT '{}',
        captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(bucket_type, bucket_key)
    );

    CREATE TABLE IF NOT EXISTS system_setting_audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        changed_keys_json TEXT NOT NULL DEFAULT '[]',
        details_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS opportunity_reject_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        opportunity_id INTEGER NOT NULL,
        listing_row_id INTEGER NOT NULL,
        reject_mode TEXT NOT NULL DEFAULT 'manual',
        note TEXT NOT NULL DEFAULT '',
        snapshot_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(listing_row_id) REFERENCES listings_raw(id)
    );

    CREATE TABLE IF NOT EXISTS seller_control_states (
        source TEXT NOT NULL,
        seller_id TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'normal',
        reason TEXT NOT NULL DEFAULT '',
        frozen_until TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(source, seller_id)
    );

    CREATE TABLE IF NOT EXISTS seller_control_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        seller_id TEXT NOT NULL,
        event_type TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        previous_state_json TEXT NOT NULL DEFAULT '{}',
        next_state_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS source_control_states (
        source TEXT NOT NULL PRIMARY KEY,
        state TEXT NOT NULL DEFAULT 'normal',
        reason TEXT NOT NULL DEFAULT '',
        frozen_until TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS source_control_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        event_type TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        previous_state_json TEXT NOT NULL DEFAULT '{}',
        next_state_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS cluster_control_states (
        risk_cluster TEXT NOT NULL PRIMARY KEY,
        state TEXT NOT NULL DEFAULT 'normal',
        reason TEXT NOT NULL DEFAULT '',
        frozen_until TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS cluster_control_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        risk_cluster TEXT NOT NULL,
        event_type TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        previous_state_json TEXT NOT NULL DEFAULT '{}',
        next_state_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS alert_delivery_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT NOT NULL DEFAULT '',
        provider TEXT NOT NULL DEFAULT '',
        channel_label TEXT NOT NULL DEFAULT '',
        delivery_stage TEXT NOT NULL DEFAULT '',
        alert_signature TEXT NOT NULL DEFAULT '',
        alert_keys_json TEXT NOT NULL DEFAULT '[]',
        alert_context_json TEXT NOT NULL DEFAULT '{}',
        alert_count INTEGER NOT NULL DEFAULT 0,
        subject TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        success INTEGER NOT NULL DEFAULT 0,
        source TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS autotrade_alert_states (
        alert_signature TEXT NOT NULL PRIMARY KEY,
        alert_code TEXT NOT NULL DEFAULT '',
        scope TEXT NOT NULL DEFAULT '',
        target TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL DEFAULT '',
        current_severity TEXT NOT NULL DEFAULT 'warning',
        first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_cleared_at TEXT,
        occurrence_count INTEGER NOT NULL DEFAULT 1,
        active INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS alert_signal_states (
        alert_key TEXT NOT NULL PRIMARY KEY,
        code TEXT NOT NULL DEFAULT '',
        scope TEXT NOT NULL DEFAULT '',
        target TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL DEFAULT '',
        last_message TEXT NOT NULL DEFAULT '',
        first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_severity TEXT NOT NULL DEFAULT 'info',
        acked_at TEXT,
        acked_by TEXT NOT NULL DEFAULT '',
        snoozed_until TEXT,
        snooze_reason TEXT NOT NULL DEFAULT '',
        incident_owner TEXT NOT NULL DEFAULT '',
        incident_status TEXT NOT NULL DEFAULT 'open',
        incident_priority TEXT NOT NULL DEFAULT '',
        incident_sla_due_at TEXT,
        latest_case_note TEXT NOT NULL DEFAULT '',
        last_case_actor TEXT NOT NULL DEFAULT '',
        last_case_updated_at TEXT,
        resolved_at TEXT
    );

    CREATE TABLE IF NOT EXISTS alert_signal_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_key TEXT NOT NULL,
        action TEXT NOT NULL DEFAULT '',
        actor TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        previous_state_json TEXT NOT NULL DEFAULT '{}',
        next_state_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS seller_control_presets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        base_preset TEXT NOT NULL DEFAULT 'all',
        source_filter TEXT NOT NULL DEFAULT '',
        action TEXT NOT NULL DEFAULT 'observe',
        reason TEXT NOT NULL DEFAULT '',
        duration_hours INTEGER,
        last_applied_at TEXT,
        last_applied_action TEXT NOT NULL DEFAULT '',
        last_applied_by TEXT NOT NULL DEFAULT '',
        last_matched_count INTEGER NOT NULL DEFAULT 0,
        last_processed_count INTEGER NOT NULL DEFAULT 0,
        last_matched_items_json TEXT NOT NULL DEFAULT '[]',
        created_by TEXT NOT NULL DEFAULT '',
        updated_by TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS seller_control_preset_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        preset_id INTEGER NOT NULL,
        action TEXT NOT NULL DEFAULT '',
        actor TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        duration_hours INTEGER,
        matched_count INTEGER NOT NULL DEFAULT 0,
        processed_count INTEGER NOT NULL DEFAULT 0,
        matched_items_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(preset_id) REFERENCES seller_control_presets(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT UNIQUE,
        password_hash TEXT NOT NULL,
        nickname TEXT NOT NULL DEFAULT '',
        role TEXT NOT NULL DEFAULT 'user',
        is_active INTEGER NOT NULL DEFAULT 1,
        is_seeded_admin INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS auth_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_no TEXT NOT NULL UNIQUE,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'general',
        priority TEXT NOT NULL DEFAULT 'normal',
        status TEXT NOT NULL DEFAULT 'open',
        description TEXT NOT NULL DEFAULT '',
        admin_assignee TEXT NOT NULL DEFAULT '',
        last_reply_by TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        closed_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS support_ticket_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL,
        author_user_id INTEGER NOT NULL,
        author_role TEXT NOT NULL DEFAULT 'user',
        is_internal INTEGER NOT NULL DEFAULT 0,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(ticket_id) REFERENCES support_tickets(id) ON DELETE CASCADE,
        FOREIGN KEY(author_user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_sales_title ON sales_raw(title);
    DROP INDEX IF EXISTS idx_listings_status;
    CREATE INDEX IF NOT EXISTS idx_listings_status_listed_at
        ON listings_raw(status, listed_at DESC);
    CREATE INDEX IF NOT EXISTS idx_listings_source_seller_status_price
        ON listings_raw(source, COALESCE(seller_id, ''), status, ROUND(list_price, 2));
    DROP INDEX IF EXISTS idx_opp_status;
    CREATE INDEX IF NOT EXISTS idx_opportunities_status_score
        ON opportunities(status, score DESC);
    CREATE INDEX IF NOT EXISTS idx_trades_status_updated
        ON trades(status, updated_at DESC);
    CREATE INDEX IF NOT EXISTS idx_validation_baseline_snapshots_bucket
        ON validation_baseline_snapshots(bucket_type, captured_at DESC);
    CREATE INDEX IF NOT EXISTS idx_forward_validation_batches_status_created
        ON forward_validation_batches(status, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_forward_validation_trades_batch_trade
        ON forward_validation_trades(batch_id, trade_id);
    CREATE INDEX IF NOT EXISTS idx_valuation_records_listing_row_id_id
        ON valuation_records(listing_row_id, id DESC);
    DROP INDEX IF EXISTS idx_execution_logs_trade_id;
    DROP INDEX IF EXISTS idx_execution_logs_action_created;
    CREATE INDEX IF NOT EXISTS idx_execution_logs_trade_action_id
        ON execution_logs(trade_id, action, id DESC);
    CREATE INDEX IF NOT EXISTS idx_autotrade_tuning_events_created
        ON autotrade_tuning_events(id DESC);
    CREATE INDEX IF NOT EXISTS idx_autotrade_tuning_events_rollback
        ON autotrade_tuning_events(rollback_of_event_id);
    CREATE INDEX IF NOT EXISTS idx_autotrade_tuning_activity_created
        ON autotrade_tuning_activity(id DESC);
    CREATE INDEX IF NOT EXISTS idx_autotrade_tuning_activity_related_event
        ON autotrade_tuning_activity(related_event_id);
    CREATE INDEX IF NOT EXISTS idx_system_setting_audit_logs_created
        ON system_setting_audit_logs(id DESC);
    CREATE INDEX IF NOT EXISTS idx_opp_reject_logs_opp_id ON opportunity_reject_logs(opportunity_id);
    CREATE INDEX IF NOT EXISTS idx_opp_reject_logs_created ON opportunity_reject_logs(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_seller_control_states_state
        ON seller_control_states(state, frozen_until);
    CREATE INDEX IF NOT EXISTS idx_seller_control_events_created
        ON seller_control_events(id DESC);
    CREATE INDEX IF NOT EXISTS idx_source_control_states_state
        ON source_control_states(state, frozen_until);
    CREATE INDEX IF NOT EXISTS idx_source_control_events_created
        ON source_control_events(id DESC);
    CREATE INDEX IF NOT EXISTS idx_cluster_control_states_state
        ON cluster_control_states(state, frozen_until);
    CREATE INDEX IF NOT EXISTS idx_cluster_control_events_created
        ON cluster_control_events(id DESC);
    CREATE INDEX IF NOT EXISTS idx_alert_delivery_events_channel_created
        ON alert_delivery_events(channel, id DESC);
    CREATE INDEX IF NOT EXISTS idx_alert_delivery_events_signature_created
        ON alert_delivery_events(channel, alert_signature, id DESC);
    CREATE INDEX IF NOT EXISTS idx_autotrade_alert_states_active_updated
        ON autotrade_alert_states(active, updated_at DESC);
    CREATE INDEX IF NOT EXISTS idx_alert_signal_states_active
        ON alert_signal_states(resolved_at, last_seen_at DESC);
    CREATE INDEX IF NOT EXISTS idx_alert_signal_events_created
        ON alert_signal_events(id DESC);
    CREATE INDEX IF NOT EXISTS idx_alert_signal_events_key_created
        ON alert_signal_events(alert_key, id DESC);
    CREATE INDEX IF NOT EXISTS idx_seller_control_presets_updated
        ON seller_control_presets(updated_at DESC);
    CREATE INDEX IF NOT EXISTS idx_seller_control_preset_runs_preset_created
        ON seller_control_preset_runs(preset_id, id DESC);
    CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id);
    CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires ON auth_sessions(expires_at);
    CREATE INDEX IF NOT EXISTS idx_support_tickets_user_id ON support_tickets(user_id);
    CREATE INDEX IF NOT EXISTS idx_support_tickets_status_updated ON support_tickets(status, updated_at DESC);
    CREATE INDEX IF NOT EXISTS idx_support_ticket_messages_ticket_id ON support_ticket_messages(ticket_id, created_at ASC);
    """
    with get_conn() as conn:
        conn.executescript(ddl)
        _ensure_table_columns(conn, "sales_raw", {
            "normalized_title": "normalized_title TEXT NOT NULL DEFAULT ''",
            "normalized_key": "normalized_key TEXT NOT NULL DEFAULT ''",
            "item_type": "item_type TEXT NOT NULL DEFAULT 'unknown'",
            "noise_flags_json": "noise_flags_json TEXT NOT NULL DEFAULT '[]'",
            "normalization_confidence": "normalization_confidence REAL NOT NULL DEFAULT 0.0",
            "normalization_blocked": "normalization_blocked INTEGER NOT NULL DEFAULT 0",
            "normalization_reason": "normalization_reason TEXT NOT NULL DEFAULT ''",
            "normalization_version": "normalization_version TEXT NOT NULL DEFAULT ''",
        })
        _ensure_table_columns(conn, "listings_raw", {
            "normalized_title": "normalized_title TEXT NOT NULL DEFAULT ''",
            "normalized_key": "normalized_key TEXT NOT NULL DEFAULT ''",
            "item_type": "item_type TEXT NOT NULL DEFAULT 'unknown'",
            "noise_flags_json": "noise_flags_json TEXT NOT NULL DEFAULT '[]'",
            "normalization_confidence": "normalization_confidence REAL NOT NULL DEFAULT 0.0",
            "normalization_blocked": "normalization_blocked INTEGER NOT NULL DEFAULT 0",
            "normalization_reason": "normalization_reason TEXT NOT NULL DEFAULT ''",
            "normalization_version": "normalization_version TEXT NOT NULL DEFAULT ''",
        })
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_listings_normalized_key_status
            ON listings_raw(normalized_key, status, listed_at DESC)
            """
        )
        _ensure_table_columns(conn, "seller_control_presets", {
            "last_applied_at": "last_applied_at TEXT",
            "last_applied_action": "last_applied_action TEXT NOT NULL DEFAULT ''",
            "last_applied_by": "last_applied_by TEXT NOT NULL DEFAULT ''",
            "last_matched_count": "last_matched_count INTEGER NOT NULL DEFAULT 0",
            "last_processed_count": "last_processed_count INTEGER NOT NULL DEFAULT 0",
            "last_matched_items_json": "last_matched_items_json TEXT NOT NULL DEFAULT '[]'",
        })
        _ensure_table_columns(conn, "alert_signal_states", {
            "acked_at": "acked_at TEXT",
            "acked_by": "acked_by TEXT NOT NULL DEFAULT ''",
            "snoozed_until": "snoozed_until TEXT",
            "snooze_reason": "snooze_reason TEXT NOT NULL DEFAULT ''",
            "incident_owner": "incident_owner TEXT NOT NULL DEFAULT ''",
            "incident_status": "incident_status TEXT NOT NULL DEFAULT 'open'",
            "incident_priority": "incident_priority TEXT NOT NULL DEFAULT ''",
            "incident_sla_due_at": "incident_sla_due_at TEXT",
            "latest_case_note": "latest_case_note TEXT NOT NULL DEFAULT ''",
            "last_case_actor": "last_case_actor TEXT NOT NULL DEFAULT ''",
            "last_case_updated_at": "last_case_updated_at TEXT",
        })
        _ensure_table_columns(conn, "alert_delivery_events", {
            "provider": "provider TEXT NOT NULL DEFAULT ''",
            "channel_label": "channel_label TEXT NOT NULL DEFAULT ''",
            "delivery_stage": "delivery_stage TEXT NOT NULL DEFAULT ''",
            "alert_keys_json": "alert_keys_json TEXT NOT NULL DEFAULT '[]'",
            "alert_context_json": "alert_context_json TEXT NOT NULL DEFAULT '{}'",
        })
        _ensure_seed_admin(conn)
        _ensure_trade_uniqueness(conn)
