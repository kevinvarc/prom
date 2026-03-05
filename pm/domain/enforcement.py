import sqlite3


def log_decision(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: int,
    actor_id: int,
    kind: str,
    reason: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    pending_approval: int = 0,
) -> int:
    conn.execute(
        "INSERT INTO decisions (entity_type, entity_id, actor_id, kind, reason, old_value, new_value, pending_approval) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (entity_type, entity_id, actor_id, kind, reason or "", old_value, new_value, pending_approval),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
