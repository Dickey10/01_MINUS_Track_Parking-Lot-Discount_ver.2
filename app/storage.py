import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.security import hash_password


def utc_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _db_path() -> Path:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connect():
    conn = sqlite3.connect(_db_path(), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS divisions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL UNIQUE,
              is_active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accounts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              display_name TEXT NOT NULL,
              division TEXT NOT NULL DEFAULT '',
              department TEXT NOT NULL DEFAULT '',
              role TEXT NOT NULL DEFAULT 'user',
              is_active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS departments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL UNIQUE,
              is_active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS email_recipients (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              email TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL DEFAULT '',
              is_active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS parking_applications (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              car_number TEXT NOT NULL,
              entry_time TEXT NOT NULL,
              dept TEXT NOT NULL,
              requester TEXT NOT NULL,
              visitor_company TEXT NOT NULL DEFAULT '',
              visit_purpose TEXT NOT NULL,
              elapsed_minutes INTEGER NOT NULL DEFAULT 0,
              effective_minutes INTEGER NOT NULL DEFAULT 0,
              coupon_30_count INTEGER NOT NULL DEFAULT 0,
              coupon_60_count INTEGER NOT NULL DEFAULT 0,
              total_discount_minutes INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'pending',
              failure_reason TEXT NOT NULL DEFAULT '',
              screenshot_path TEXT NOT NULL DEFAULT '',
              email_status TEXT NOT NULL DEFAULT 'not_sent',
              created_by INTEGER,
              processed_by INTEGER,
              processed_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(created_by) REFERENCES accounts(id),
              FOREIGN KEY(processed_by) REFERENCES accounts(id)
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              actor_id INTEGER,
              action TEXT NOT NULL,
              target_type TEXT NOT NULL,
              target_id INTEGER,
              detail TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              FOREIGN KEY(actor_id) REFERENCES accounts(id)
            );
            """
        )
        _migrate_accounts(conn)
        _ensure_column(conn, "parking_applications", "division", "TEXT NOT NULL DEFAULT ''")
        admin = conn.execute(
            "SELECT id FROM accounts WHERE username = ?", (settings.admin_username,)
        ).fetchone()
        if not admin:
            now = utc_now()
            conn.execute(
                """
                INSERT INTO accounts
                  (username, password_hash, display_name, division, department, role, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'super_admin', 1, ?, ?)
                """,
                (
                    settings.admin_username,
                    hash_password(settings.admin_password),
                    "System Admin",
                    "Management Division",
                    "General Affairs",
                    now,
                    now,
                ),
            )


def _table_columns(conn, table: str) -> list[str]:
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _ensure_column(conn, table: str, column: str, definition: str) -> None:
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _migrate_accounts(conn) -> None:
    columns = _table_columns(conn, "accounts")
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'accounts'"
    ).fetchone()["sql"]
    if "CHECK(role IN ('admin', 'manager'))" not in sql and "division" in columns:
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TABLE IF EXISTS accounts_new")
    conn.execute("ALTER TABLE accounts RENAME TO accounts_old")
    conn.executescript(
        """
        CREATE TABLE accounts_new (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,
          display_name TEXT NOT NULL,
          division TEXT NOT NULL DEFAULT '',
          department TEXT NOT NULL DEFAULT '',
          role TEXT NOT NULL DEFAULT 'user',
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """
    )
    old_columns = _table_columns(conn, "accounts_old")
    division_expr = "division" if "division" in old_columns else "''"
    rows = conn.execute(
        f"""
        SELECT id, username, password_hash, display_name, {division_expr} AS division,
               department, role, is_active, created_at, updated_at
        FROM accounts_old
        """
    ).fetchall()
    for row in rows:
        role = row["role"]
        if role == "admin":
            role = "super_admin"
        elif role == "manager":
            role = "user"
        if not row["is_active"]:
            role = "inactive"
        conn.execute(
            """
            INSERT INTO accounts_new
              (id, username, password_hash, display_name, division, department, role, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["username"],
                row["password_hash"],
                row["display_name"],
                row["division"],
                row["department"],
                role,
                row["is_active"],
                row["created_at"],
                row["updated_at"],
            ),
        )
    conn.execute("DROP TABLE accounts_old")
    conn.execute("ALTER TABLE accounts_new RENAME TO accounts")
    conn.execute("PRAGMA foreign_keys = ON")


def audit(actor_id: int | None, action: str, target_type: str, target_id: int | None, detail: str = "") -> None:
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO audit_logs (actor_id, action, target_type, target_id, detail, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (actor_id, action, target_type, target_id, detail, utc_now()),
            )
    except sqlite3.OperationalError as exc:
        print(f"[audit] skipped: {exc}")
