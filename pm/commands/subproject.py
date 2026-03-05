import typer
from pm.db import get_connection
from pm.output import emit, use_pretty
from pm.utils import get_actor_id, slugify

app = typer.Typer()


def _project_id_by_slug(conn, project_slug: str) -> int | None:
    cur = conn.execute("SELECT id FROM projects WHERE slug = ?", (project_slug,))
    row = cur.fetchone()
    return int(row["id"]) if row else None


def _subproject_by_slugs(conn, project_slug: str, subproject_slug: str) -> dict | None:
    pid = _project_id_by_slug(conn, project_slug)
    if not pid:
        return None
    cur = conn.execute(
        "SELECT id, project_id, slug, name, description, status, waiting, waiting_reason, summary, last_task_movement_at, created_at, updated_at FROM subprojects WHERE project_id = ? AND slug = ?",
        (pid, subproject_slug),
    )
    row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["created_at"] = str(d["created_at"])
    d["updated_at"] = str(d["updated_at"])
    d["waiting"] = bool(d["waiting"])
    return d


@app.command("add")
def add_cmd(
    project_slug: str = typer.Argument(...),
    name: str = typer.Argument(...),
    actor: str = typer.Option(..., "--actor"),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
    slug = slugify(name)
    conn = get_connection()
    try:
        actor_id = get_actor_id(conn, actor)
        if not actor_id:
            typer.echo(f"Unknown actor: {actor}", err=True)
            raise typer.Exit(1)
        pid = _project_id_by_slug(conn, project_slug)
        if not pid:
            typer.echo(f"Project not found: {project_slug}", err=True)
            raise typer.Exit(1)
        conn.execute(
            "INSERT INTO subprojects (project_id, slug, name, description, status, waiting, summary) VALUES (?, ?, ?, '', 'active', 0, '')",
            (pid, slug, name),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, project_id, slug, name, description, status, waiting, waiting_reason, summary, last_task_movement_at, created_at, updated_at FROM subprojects WHERE id = last_insert_rowid()"
        ).fetchone()
        out = dict(row)
        out["created_at"] = str(out["created_at"])
        out["updated_at"] = str(out["updated_at"])
        out["waiting"] = bool(out["waiting"])
        emit(out, use_pretty(pretty))
    except Exception as e:
        if "UNIQUE" in str(e):
            typer.echo(f"Subproject slug '{slug}' already exists in project.", err=True)
            raise typer.Exit(1)
        raise
    finally:
        conn.close()


@app.command("list")
def list_cmd(project_slug: str = typer.Argument(...), pretty: bool = typer.Option(None, "--pretty")) -> None:
    conn = get_connection()
    try:
        pid = _project_id_by_slug(conn, project_slug)
        if not pid:
            typer.echo(f"Project not found: {project_slug}", err=True)
            raise typer.Exit(1)
        cur = conn.execute(
            "SELECT s.id, s.slug, s.name, s.description, s.status, s.waiting, s.waiting_reason, s.summary, s.last_task_movement_at, s.created_at, s.updated_at, (SELECT COUNT(*) FROM tasks t WHERE t.subproject_id = s.id) AS task_count FROM subprojects s WHERE s.project_id = ? ORDER BY s.slug",
            (pid,),
        )
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["created_at"] = str(d["created_at"])
            d["updated_at"] = str(d["updated_at"])
            d["waiting"] = bool(d["waiting"])
            rows.append(d)
        emit(rows, use_pretty(pretty))
    finally:
        conn.close()


@app.command("get")
def get_cmd(
    project_slug: str = typer.Argument(...),
    subproject_slug: str = typer.Argument(...),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
    conn = get_connection()
    try:
        sub = _subproject_by_slugs(conn, project_slug, subproject_slug)
        if not sub:
            typer.echo("Subproject not found.", err=True)
            raise typer.Exit(1)
        cur = conn.execute(
            "SELECT id, subproject_id, title, description, status, actor_id, done_at, created_at, updated_at FROM tasks WHERE subproject_id = ? ORDER BY id",
            (sub["id"],),
        )
        sub["tasks"] = [dict(t) for t in cur.fetchall()]
        for t in sub["tasks"]:
            t["created_at"] = str(t["created_at"])
            t["updated_at"] = str(t["updated_at"])
            if t.get("done_at"):
                t["done_at"] = str(t["done_at"])
        dec_cur = conn.execute(
            "SELECT id, entity_type, entity_id, actor_id, at, kind, reason, pending_approval, created_at FROM decisions WHERE entity_type = 'subproject' AND entity_id = ? ORDER BY created_at DESC LIMIT 20",
            (sub["id"],),
        )
        sub["recent_decisions"] = [dict(d) for d in dec_cur.fetchall()]
        for d in sub["recent_decisions"]:
            d["pending_approval"] = bool(d["pending_approval"])
            d["at"] = str(d["at"])
            d["created_at"] = str(d["created_at"])
        emit(sub, use_pretty(pretty))
    finally:
        conn.close()


@app.command("complete")
def complete_cmd(
    project_slug: str = typer.Argument(...),
    subproject_slug: str = typer.Argument(...),
    reason: str = typer.Option(..., "--reason"),
    actor: str = typer.Option(..., "--actor"),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
    conn = get_connection()
    try:
        actor_id = get_actor_id(conn, actor)
        if not actor_id:
            typer.echo(f"Unknown actor: {actor}", err=True)
            raise typer.Exit(1)
        sub = _subproject_by_slugs(conn, project_slug, subproject_slug)
        if not sub:
            typer.echo("Subproject not found.", err=True)
            raise typer.Exit(1)
        conn.execute(
            "INSERT INTO decisions (entity_type, entity_id, actor_id, kind, reason, old_value, new_value, pending_approval) VALUES ('subproject', ?, ?, 'status_change', ?, ?, 'completed', 0)",
            (sub["id"], actor_id, reason, sub["status"]),
        )
        conn.execute(
            "UPDATE subprojects SET status = 'completed', updated_at = datetime('now') WHERE id = ?",
            (sub["id"],),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, project_id, slug, name, description, status, waiting, waiting_reason, summary, last_task_movement_at, created_at, updated_at FROM subprojects WHERE id = ?",
            (sub["id"],),
        ).fetchone()
        out = dict(row)
        out["created_at"] = str(out["created_at"])
        out["updated_at"] = str(out["updated_at"])
        out["waiting"] = bool(out["waiting"])
        emit(out, use_pretty(pretty))
    finally:
        conn.close()


@app.command("wait")
def wait_cmd(
    project_slug: str = typer.Argument(...),
    subproject_slug: str = typer.Argument(...),
    reason: str = typer.Option(..., "--reason"),
    actor: str = typer.Option(..., "--actor"),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
    conn = get_connection()
    try:
        actor_id = get_actor_id(conn, actor)
        if not actor_id:
            typer.echo(f"Unknown actor: {actor}", err=True)
            raise typer.Exit(1)
        sub = _subproject_by_slugs(conn, project_slug, subproject_slug)
        if not sub:
            typer.echo("Subproject not found.", err=True)
            raise typer.Exit(1)
        conn.execute(
            "INSERT INTO decisions (entity_type, entity_id, actor_id, kind, reason, new_value, pending_approval) VALUES ('subproject', ?, ?, 'waiting_set', ?, ?, 0)",
            (sub["id"], actor_id, reason, reason),
        )
        conn.execute(
            "UPDATE subprojects SET waiting = 1, waiting_reason = ?, updated_at = datetime('now') WHERE id = ?",
            (reason, sub["id"]),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, project_id, slug, name, description, status, waiting, waiting_reason, summary, last_task_movement_at, created_at, updated_at FROM subprojects WHERE id = ?",
            (sub["id"],),
        ).fetchone()
        out = dict(row)
        out["created_at"] = str(out["created_at"])
        out["updated_at"] = str(out["updated_at"])
        out["waiting"] = bool(out["waiting"])
        emit(out, use_pretty(pretty))
    finally:
        conn.close()


@app.command("unwait")
def unwait_cmd(
    project_slug: str = typer.Argument(...),
    subproject_slug: str = typer.Argument(...),
    reason: str = typer.Option(..., "--reason"),
    actor: str = typer.Option(..., "--actor"),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
    conn = get_connection()
    try:
        actor_id = get_actor_id(conn, actor)
        if not actor_id:
            typer.echo(f"Unknown actor: {actor}", err=True)
            raise typer.Exit(1)
        sub = _subproject_by_slugs(conn, project_slug, subproject_slug)
        if not sub:
            typer.echo("Subproject not found.", err=True)
            raise typer.Exit(1)
        conn.execute(
            "INSERT INTO decisions (entity_type, entity_id, actor_id, kind, reason, pending_approval) VALUES ('subproject', ?, ?, 'waiting_cleared', ?, 0)",
            (sub["id"], actor_id, reason),
        )
        conn.execute(
            "UPDATE subprojects SET waiting = 0, waiting_reason = NULL, updated_at = datetime('now') WHERE id = ?",
            (sub["id"],),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, project_id, slug, name, description, status, waiting, waiting_reason, summary, last_task_movement_at, created_at, updated_at FROM subprojects WHERE id = ?",
            (sub["id"],),
        ).fetchone()
        out = dict(row)
        out["created_at"] = str(out["created_at"])
        out["updated_at"] = str(out["updated_at"])
        out["waiting"] = bool(out["waiting"])
        emit(out, use_pretty(pretty))
    finally:
        conn.close()
