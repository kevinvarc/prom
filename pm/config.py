from pm.db import get_connection

DEFAULTS = {
    "days_yellow_subproject": "5",
    "days_red_subproject": "8",
    "days_waiting_warn": "4",
    "days_waiting_decision": "7",
}


def get_config(key: str) -> str:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else DEFAULTS.get(key, "")
    finally:
        conn.close()


def get_config_int(key: str) -> int:
    return int(get_config(key))


def set_config(key: str, value: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()
