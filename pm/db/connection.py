import os
import sys
import sqlite3
from pathlib import Path

DEFAULT_DB_DIR = Path(os.environ.get("PM_HOME", os.path.expanduser("~/.pm")))
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "projects.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

CONFIG_SEED = [
    ("days_yellow_subproject", "7"),
    ("days_red_subproject", "14"),
    ("days_waiting_warn", "4"),
    ("days_waiting_decision", "7"),
]


def get_db_path() -> Path:
    return Path(os.environ.get("PM_DB", str(DEFAULT_DB_PATH)))


def get_connection():
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        v = schema_version(conn)
    except Exception:
        v = 0
    if v < 1:
        init_db(conn)
        conn.executemany(
            "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
            CONFIG_SEED,
        )
        set_schema_version(conn, 1)
        conn.commit()
        if sys.stdin.isatty():
            human = input("Your name (human): ").strip()
            agent = input("Your agent name: ").strip()
            if human and agent:
                conn.execute("INSERT INTO actors (name, role) VALUES (?, ?)", (human, "human"))
                conn.execute("INSERT INTO actors (name, role) VALUES (?, ?)", (agent, "agent"))
                conn.commit()
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()


def schema_version(conn: sqlite3.Connection) -> int:
    cur = conn.execute("SELECT version FROM schema_version LIMIT 1")
    row = cur.fetchone()
    return int(row[0]) if row else 0


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    conn.commit()
