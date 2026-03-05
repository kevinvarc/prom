import typer
from pm.db import get_connection
from pm.output import emit, use_pretty
from pm.utils import get_actor_id

app = typer.Typer()


def _subproject_id_by_slugs(conn, project_slug: str, subproject_slug: str) -> int | None:
    cur = conn.execute(
        "SELECT s.id FROM subprojects s JOIN projects p ON s.project_id = p.id WHERE p.slug = ? AND s.slug = ?",
        (project_slug, subproject_slug),
    )
    row = cur.fetchone()
    return int(row["id"]) if row else None


def _task_by_id(conn, task_id: int) -> dict | None:
    cur = conn.execute(
        "SELECT t.id, t.subproject_id, t.title, t.description, t.status, t.actor_id, t.done_at, t.created_at, t.updated_at, s.project_id FROM tasks t JOIN subprojects s ON t.subproject_id = s.id WHERE t.id = ?",
        (task_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["created_at"] = str(d["created_at"])
    d["updated_at"] = str(d["updated_at"])
    if d.get("done_at"):
        d["done_at"] = str(d["done_at"])
    return d


@app.command("add")
def add_cmd(
    project_slug: str = typer.Argument(...),
    subproject_slug: str = typer.Argument(...),
    title: str = typer.Argument(...),
    actor: str = typer.Option(..., "--actor"),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
    conn = get_connection()
    try:
        actor_id = get_actor_id(conn, actor)
        if not actor_id:
            typer.echo(f"Unknown actor: {actor}", err=True)
            raise typer.Exit(1)
        sid = _subproject_id_by_slugs(conn, project_slug, subproject_slug)
        if not sid:
            typer.echo("Project or subproject not found.", err=True)
            raise typer.Exit(1)
        conn.execute(
            "INSERT INTO tasks (subproject_id, title, description, status, actor_id) VALUES (?, ?, '', 'open', ?)",
            (sid, title, actor_id),
        )
        conn.execute(
            "UPDATE subprojects SET last_task_movement_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (sid,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, subproject_id, title, description, status, actor_id, done_at, created_at, updated_at FROM tasks WHERE id = last_insert_rowid()"
        ).fetchone()
        out = dict(row)
        out["created_at"] = str(out["created_at"])
        out["updated_at"] = str(out["updated_at"])
        emit(out, use_pretty(pretty))
    finally:
        conn.close()


@app.command("list")
def list_cmd(
    project_slug: str = typer.Argument(...),
    subproject_slug: str = typer.Argument(...),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
    conn = get_connection()
    try:
        sid = _subproject_id_by_slugs(conn, project_slug, subproject_slug)
        if not sid:
            typer.echo("Project or subproject not found.", err=True)
            raise typer.Exit(1)
        cur = conn.execute(
            "SELECT id, subproject_id, title, description, status, actor_id, done_at, created_at, updated_at FROM tasks WHERE subproject_id = ? ORDER BY id",
            (sid,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r["created_at"] = str(r["created_at"])
            r["updated_at"] = str(r["updated_at"])
            if r.get("done_at"):
                r["done_at"] = str(r["done_at"])
        emit(rows, use_pretty(pretty))
    finally:
        conn.close()


@app.command("start")
def start_cmd(
    task_id: int = typer.Argument(...),
    actor: str = typer.Option(..., "--actor"),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
    conn = get_connection()
    try:
        task = _task_by_id(conn, task_id)
        if not task:
            typer.echo("Task not found.", err=True)
            raise typer.Exit(1)
        if task["status"] in ("done", "cancelled"):
            typer.echo("Task is already done or cancelled.", err=True)
            raise typer.Exit(1)
        conn.execute(
            "UPDATE tasks SET status = 'in_progress', updated_at = datetime('now') WHERE id = ?",
            (task_id,),
        )
        conn.execute(
            "UPDATE subprojects SET last_task_movement_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (task["subproject_id"],),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, subproject_id, title, description, status, actor_id, done_at, created_at, updated_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        out = dict(row)
        out["created_at"] = str(out["created_at"])
        out["updated_at"] = str(out["updated_at"])
        emit(out, use_pretty(pretty))
    finally:
        conn.close()


@app.command("done")
def done_cmd(
    task_id: int = typer.Argument(...),
    actor: str = typer.Option(..., "--actor"),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
    conn = get_connection()
    try:
        actor_id = get_actor_id(conn, actor)
        if not actor_id:
            typer.echo(f"Unknown actor: {actor}", err=True)
            raise typer.Exit(1)
        task = _task_by_id(conn, task_id)
        if not task:
            typer.echo("Task not found.", err=True)
            raise typer.Exit(1)
        conn.execute(
            "UPDATE tasks SET status = 'done', done_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (task_id,),
        )
        conn.execute(
            "UPDATE subprojects SET last_task_movement_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (task["subproject_id"],),
        )
        desc = "Task completed: " + (task.get("title") or str(task_id))
        conn.execute(
            "INSERT INTO done_log (task_id, subproject_id, project_id, actor_id, description) VALUES (?, ?, ?, ?, ?)",
            (task_id, task["subproject_id"], task["project_id"], actor_id, desc),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, subproject_id, title, description, status, actor_id, done_at, created_at, updated_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        out = dict(row)
        out["created_at"] = str(out["created_at"])
        out["updated_at"] = str(out["updated_at"])
        out["done_at"] = str(out["done_at"])
        emit(out, use_pretty(pretty))
    finally:
        conn.close()


@app.command("change")
def change_cmd(
    task_id: int = typer.Argument(...),
    reason: str = typer.Option(..., "--reason"),
    actor: str = typer.Option(..., "--actor"),
    title: str = typer.Option(None, "--title"),
    description: str = typer.Option(None, "--description"),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
    conn = get_connection()
    try:
        actor_id = get_actor_id(conn, actor)
        if not actor_id:
            typer.echo(f"Unknown actor: {actor}", err=True)
            raise typer.Exit(1)
        task = _task_by_id(conn, task_id)
        if not task:
            typer.echo("Task not found.", err=True)
            raise typer.Exit(1)
        if task["status"] in ("done", "cancelled"):
            typer.echo("Cannot change a done or cancelled task.", err=True)
            raise typer.Exit(1)
        new_title = title if title is not None else task.get("title") or ""
        new_desc = description if description is not None else task.get("description") or ""
        conn.execute(
            "INSERT INTO decisions (entity_type, entity_id, actor_id, kind, reason, old_value, new_value, pending_approval) VALUES ('task', ?, ?, 'task_change', ?, ?, ?, 0)",
            (task_id, actor_id, reason, task.get("title") or "", new_title),
        )
        if title is not None or description is not None:
            conn.execute(
                "UPDATE tasks SET title = ?, description = ?, updated_at = datetime('now') WHERE id = ?",
                (new_title, new_desc, task_id),
            )
        conn.commit()
        row = conn.execute(
            "SELECT id, subproject_id, title, description, status, actor_id, done_at, created_at, updated_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        out = dict(row)
        out["created_at"] = str(out["created_at"])
        out["updated_at"] = str(out["updated_at"])
        emit(out, use_pretty(pretty))
    finally:
        conn.close()
