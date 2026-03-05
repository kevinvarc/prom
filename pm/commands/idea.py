import typer
from pm.db import get_connection
from pm.output import emit, use_pretty
from pm.utils import get_actor_id, slugify

app = typer.Typer()


def _project_id_by_slug(conn, project_slug: str) -> int | None:
    cur = conn.execute("SELECT id FROM projects WHERE slug = ?", (project_slug,))
    row = cur.fetchone()
    return int(row["id"]) if row else None


@app.command("add")
def add_cmd(
    project_slug: str = typer.Argument(...),
    title: str = typer.Argument(...),
    body: str = typer.Option(None, "--body"),
    actor: str = typer.Option(..., "--actor"),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
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
            "INSERT INTO ideas (project_id, title, body, actor_id) VALUES (?, ?, ?, ?)",
            (pid, title, body or "", actor_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, project_id, title, body, created_at, actor_id FROM ideas WHERE id = last_insert_rowid()"
        ).fetchone()
        out = dict(row)
        out["created_at"] = str(out["created_at"])
        emit(out, use_pretty(pretty))
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
            "SELECT id, project_id, title, body, created_at, actor_id FROM ideas WHERE project_id = ? ORDER BY created_at DESC",
            (pid,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r["created_at"] = str(r["created_at"])
        emit(rows, use_pretty(pretty))
    finally:
        conn.close()


@app.command("promote")
def promote_cmd(
    idea_id: int = typer.Argument(...),
    actor: str = typer.Option(..., "--actor"),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
    conn = get_connection()
    try:
        actor_id = get_actor_id(conn, actor)
        if not actor_id:
            typer.echo(f"Unknown actor: {actor}", err=True)
            raise typer.Exit(1)
        cur = conn.execute("SELECT id, project_id, title, body FROM ideas WHERE id = ?", (idea_id,))
        row = cur.fetchone()
        if not row:
            typer.echo("Idea not found.", err=True)
            raise typer.Exit(1)
        idea = dict(row)
        slug = slugify(idea["title"])
        conn.execute(
            "INSERT INTO decisions (entity_type, entity_id, actor_id, kind, reason, old_value, new_value, pending_approval) VALUES ('project', ?, ?, 'subproject_promoted_from_idea', 'Promoted from idea', ?, ?, 0)",
            (idea["project_id"], actor_id, str(idea_id), idea["title"]),
        )
        conn.execute(
            "INSERT INTO subprojects (project_id, slug, name, description, status, waiting, summary) VALUES (?, ?, ?, ?, 'active', 0, '')",
            (idea["project_id"], slug, idea["title"], idea["body"] or ""),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
        conn.commit()
        sub = conn.execute(
            "SELECT id, project_id, slug, name, description, status, waiting, waiting_reason, summary, last_task_movement_at, created_at, updated_at FROM subprojects WHERE id = ?",
            (new_id,),
        ).fetchone()
        out = dict(sub)
        out["created_at"] = str(out["created_at"])
        out["updated_at"] = str(out["updated_at"])
        out["waiting"] = bool(out["waiting"])
        emit(out, use_pretty(pretty))
    finally:
        conn.close()
