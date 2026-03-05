import sqlite3


def slugify(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in s.lower()).strip("-") or "x"


def get_actor_id(conn: sqlite3.Connection, name: str) -> int | None:
    cur = conn.execute("SELECT id FROM actors WHERE name = ?", (name,))
    row = cur.fetchone()
    return int(row["id"]) if row else None


def row_to_dict(row: sqlite3.Row, date_keys: list[str] | None = None) -> dict:
    d = dict(row)
    for k in date_keys or []:
        if k in d and d[k] is not None:
            d[k] = str(d[k])
    return d
