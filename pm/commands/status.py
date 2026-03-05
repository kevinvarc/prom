import typer
from pm.config import get_config_int
from pm.db import get_connection
from pm.domain.health import project_health, subproject_health
from pm.output import emit, use_pretty

app = typer.Typer()


@app.command()
def status_cmd(project_slug: str = typer.Argument(...), pretty: bool = typer.Option(None, "--pretty")) -> None:
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT id, slug, name, purpose, status, summary, created_at, updated_at FROM projects WHERE slug = ?",
            (project_slug,),
        )
        row = cur.fetchone()
        if not row:
            typer.echo(f"Project not found: {project_slug}", err=True)
            raise typer.Exit(1)
        proj = dict(row)
        proj["created_at"] = str(proj["created_at"])
        proj["updated_at"] = str(proj["updated_at"])
        days_yellow = get_config_int("days_yellow_subproject")
        days_red = get_config_int("days_red_subproject")
        sub_cur = conn.execute(
            "SELECT id, slug, name, description, status, waiting, waiting_reason, summary, last_task_movement_at, created_at, updated_at FROM subprojects WHERE project_id = ? ORDER BY slug",
            (proj["id"],),
        )
        subprojects = []
        healths = []
        for s in sub_cur.fetchall():
            sub = dict(s)
            sub["created_at"] = str(sub["created_at"])
            sub["updated_at"] = str(sub["updated_at"])
            sub["waiting"] = bool(sub["waiting"])
            task_cur = conn.execute(
                "SELECT status FROM tasks WHERE subproject_id = ? AND status IN ('open', 'in_progress')",
                (sub["id"],),
            )
            has_open = task_cur.fetchone() is not None
            h = subproject_health(
                sub.get("last_task_movement_at"),
                sub["waiting"],
                has_open,
                days_yellow,
                days_red,
            )
            sub["health"] = h
            healths.append(h)
            task_cur = conn.execute(
                "SELECT id, title, status, actor_id, done_at, created_at, updated_at FROM tasks WHERE subproject_id = ? ORDER BY id",
                (sub["id"],),
            )
            sub["tasks"] = [dict(t) for t in task_cur.fetchall()]
            for t in sub["tasks"]:
                t["created_at"] = str(t["created_at"])
                t["updated_at"] = str(t["updated_at"])
                if t.get("done_at"):
                    t["done_at"] = str(t["done_at"])
            subprojects.append(sub)
        proj["health"] = project_health(healths)
        proj["subprojects"] = subprojects
        emit(proj, use_pretty(pretty))
    finally:
        conn.close()
