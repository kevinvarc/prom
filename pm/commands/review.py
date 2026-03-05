from datetime import datetime

import typer
from pm.config import get_config_int
from pm.db import get_connection
from pm.domain.health import subproject_health, waiting_escalation
from pm.output import emit, use_pretty

app = typer.Typer()


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


@app.command()
def review_cmd(pretty: bool = typer.Option(None, "--pretty")) -> None:
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT d.id, d.task_id, d.subproject_id, d.project_id, d.actor_id, d.description, d.created_at, p.slug AS project_slug FROM done_log d JOIN projects p ON d.project_id = p.id ORDER BY d.created_at DESC LIMIT 30"
        )
        moved = [dict(r) for r in cur.fetchall()]
        for r in moved:
            r["created_at"] = str(r["created_at"])
        days_yellow = get_config_int("days_yellow_subproject")
        days_red = get_config_int("days_red_subproject")
        days_warn = get_config_int("days_waiting_warn")
        days_decision = get_config_int("days_waiting_decision")
        cur = conn.execute(
            "SELECT p.slug AS project_slug, s.id, s.slug AS subproject_slug, s.name, s.last_task_movement_at, s.waiting, s.updated_at FROM subprojects s JOIN projects p ON s.project_id = p.id WHERE s.status = 'active'"
        )
        stale = []
        waiting_esc = []
        for row in cur.fetchall():
            r = dict(row)
            r["waiting"] = bool(r["waiting"])
            task_cur = conn.execute(
                "SELECT 1 FROM tasks WHERE subproject_id = ? AND status IN ('open', 'in_progress') LIMIT 1",
                (r["id"],),
            )
            has_open = task_cur.fetchone() is not None
            h = subproject_health(
                r.get("last_task_movement_at"),
                r["waiting"],
                has_open,
                days_yellow,
                days_red,
            )
            if h in ("yellow", "red"):
                movement = r.get("last_task_movement_at")
                dt = _parse_iso(movement) if movement else None
                days_stale = (datetime.utcnow() - dt).days if dt else days_yellow
                stale.append(
                    {
                        "project_slug": r["project_slug"],
                        "subproject_slug": r["subproject_slug"],
                        "health": h,
                        "days_stale": days_stale,
                    }
                )
            if r["waiting"] and r.get("updated_at"):
                esc = waiting_escalation(r["updated_at"], days_warn, days_decision)
                if esc["warn"] or esc["require_decision"]:
                    waiting_esc.append(
                        {
                            "project_slug": r["project_slug"],
                            "subproject_slug": r["subproject_slug"],
                            "warn": esc["warn"],
                            "require_decision": esc["require_decision"],
                        }
                    )
        pending_cur = conn.execute(
            "SELECT id, entity_type, entity_id, actor_id, kind, reason, created_at FROM decisions WHERE pending_approval = 1 ORDER BY created_at"
        )
        pending = [dict(r) for r in pending_cur.fetchall()]
        for p in pending:
            p["created_at"] = str(p["created_at"])
        emit(
            {
                "moved": moved,
                "stale": stale,
                "waiting_escalation": waiting_esc,
                "pending_approvals": pending,
            },
            use_pretty(pretty),
        )
    finally:
        conn.close()
