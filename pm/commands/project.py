import typer
from pm.config import get_config_int
from pm.db import get_connection
from pm.domain.health import project_health, subproject_health
from pm.output import emit, use_pretty
from pm.utils import get_actor_id, slugify


@app.command("add")
def add_cmd(
    slug: str = typer.Argument(...),
    name: str = typer.Option(..., "--name"),
    purpose: str = typer.Option(..., "--purpose"),
    actor: str = typer.Option(..., "--actor"),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
    slug = slugify(slug)
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM actors WHERE name = ?", (actor,))
        actor_row = cur.fetchone()
        if not actor_row:
            typer.echo(f"Unknown actor: {actor}", err=True)
            raise typer.Exit(1)
        conn.execute(
            "INSERT INTO projects (slug, name, purpose, status, summary) VALUES (?, ?, ?, 'active', '')",
            (slug, name, purpose),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, slug, name, purpose, status, summary, created_at, updated_at FROM projects WHERE id = last_insert_rowid()"
        ).fetchone()
        out = dict(row)
        out["created_at"] = str(out["created_at"])
        out["updated_at"] = str(out["updated_at"])
        emit(out, use_pretty(pretty))
    except Exception as e:
        if "UNIQUE" in str(e):
            typer.echo(f"Project slug '{slug}' already exists.", err=True)
            raise typer.Exit(1)
        raise
    finally:
        conn.close()


@app.command("list")
def list_cmd(pretty: bool = typer.Option(None, "--pretty")) -> None:
    conn = get_connection()
    try:
        days_yellow = get_config_int("days_yellow_subproject")
        days_red = get_config_int("days_red_subproject")
        cur = conn.execute(
            "SELECT id, slug, name, purpose, status, summary, created_at, updated_at FROM projects ORDER BY updated_at DESC"
        )
        rows = []
        for r in cur.fetchall():
            proj = dict(r)
            proj["created_at"] = str(proj["created_at"])
            proj["updated_at"] = str(proj["updated_at"])
            sub_cur = conn.execute(
                "SELECT id, last_task_movement_at, waiting FROM subprojects WHERE project_id = ? AND status = 'active'",
                (proj["id"],),
            )
            healths = []
            for s in sub_cur.fetchall():
                sub = dict(s)
                sub["waiting"] = bool(sub["waiting"])
                tcur = conn.execute(
                    "SELECT 1 FROM tasks WHERE subproject_id = ? AND status IN ('open', 'in_progress') LIMIT 1",
                    (sub["id"],),
                )
                has_open = tcur.fetchone() is not None
                healths.append(
                    subproject_health(
                        sub.get("last_task_movement_at"),
                        sub["waiting"],
                        has_open,
                        days_yellow,
                        days_red,
                    )
                )
            proj["health"] = project_health(healths)
            rows.append(proj)
        emit(rows, use_pretty(pretty))
    finally:
        conn.close()


@app.command("get")
def get_cmd(slug: str = typer.Argument(...), pretty: bool = typer.Option(None, "--pretty")) -> None:
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT id, slug, name, purpose, status, summary, created_at, updated_at FROM projects WHERE slug = ?",
            (slug,),
        )
        row = cur.fetchone()
        if not row:
            typer.echo(f"Project not found: {slug}", err=True)
            raise typer.Exit(1)
        out = dict(row)
        out["created_at"] = str(out["created_at"])
        out["updated_at"] = str(out["updated_at"])
        sub_cur = conn.execute(
            "SELECT id, slug, name, description, status, waiting, waiting_reason, summary, last_task_movement_at, created_at, updated_at FROM subprojects WHERE project_id = ? ORDER BY slug",
            (out["id"],),
        )
        subs = [dict(s) for s in sub_cur.fetchall()]
        days_yellow = get_config_int("days_yellow_subproject")
        days_red = get_config_int("days_red_subproject")
        healths = []
        for s in subs:
            s["created_at"] = str(s["created_at"])
            s["updated_at"] = str(s["updated_at"])
            s["waiting"] = bool(s["waiting"])
            tcur = conn.execute(
                "SELECT 1 FROM tasks WHERE subproject_id = ? AND status IN ('open', 'in_progress') LIMIT 1",
                (s["id"],),
            )
            has_open = tcur.fetchone() is not None
            h = subproject_health(
                s.get("last_task_movement_at"),
                s["waiting"],
                has_open,
                days_yellow,
                days_red,
            )
            s["health"] = h
            if s.get("status") == "active":
                healths.append(h)
        out["health"] = project_health(healths)
        out["subprojects"] = subs
        dec_cur = conn.execute(
            "SELECT d.id, d.entity_type, d.entity_id, d.actor_id, d.at, d.kind, d.reason, d.pending_approval, d.created_at FROM decisions d JOIN projects p ON (d.entity_type = 'project' AND d.entity_id = p.id) WHERE p.slug = ? ORDER BY d.created_at DESC LIMIT 20",
            (slug,),
        )
        out["recent_decisions"] = [dict(d) for d in dec_cur.fetchall()]
        for d in out["recent_decisions"]:
            d["pending_approval"] = bool(d["pending_approval"])
            d["at"] = str(d["at"])
            d["created_at"] = str(d["created_at"])
        emit(out, use_pretty(pretty))
    finally:
        conn.close()


@app.command("update")
def update_cmd(
    slug: str = typer.Argument(...),
    summary: str = typer.Option(None, "--summary"),
    purpose: str = typer.Option(None, "--purpose"),
    actor: str = typer.Option(..., "--actor"),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
    conn = get_connection()
    try:
        actor_id = get_actor_id(conn, actor)
        if not actor_id:
            typer.echo(f"Unknown actor: {actor}", err=True)
            raise typer.Exit(1)
        cur = conn.execute("SELECT id, purpose, status, summary FROM projects WHERE slug = ?", (slug,))
        row = cur.fetchone()
        if not row:
            typer.echo(f"Project not found: {slug}", err=True)
            raise typer.Exit(1)
        proj = dict(row)
        if summary is not None:
            conn.execute(
                "UPDATE projects SET summary = ?, updated_at = datetime('now') WHERE id = ?",
                (summary, proj["id"]),
            )
        if purpose is not None:
            conn.execute(
                "INSERT INTO decisions (entity_type, entity_id, actor_id, kind, reason, old_value, new_value, pending_approval) VALUES ('project', ?, ?, 'purpose_change', 'Proposed purpose change', ?, ?, 1)",
                (proj["id"], actor_id, proj["purpose"] or "", purpose),
            )
        conn.commit()
        row = conn.execute(
            "SELECT id, slug, name, purpose, status, summary, created_at, updated_at FROM projects WHERE slug = ?",
            (slug,),
        ).fetchone()
        out = dict(row)
        out["created_at"] = str(out["created_at"])
        out["updated_at"] = str(out["updated_at"])
        emit(out, use_pretty(pretty))
    finally:
        conn.close()


@app.command("complete")
def complete_cmd(
    slug: str = typer.Argument(...),
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
        cur = conn.execute("SELECT id, status FROM projects WHERE slug = ?", (slug,))
        row = cur.fetchone()
        if not row:
            typer.echo(f"Project not found: {slug}", err=True)
            raise typer.Exit(1)
        proj = dict(row)
        sub_cur = conn.execute("SELECT id, status FROM subprojects WHERE project_id = ?", (proj["id"],))
        subs = list(sub_cur.fetchall())
        if subs and any(s["status"] != "completed" for s in subs):
            typer.echo("All subprojects must be completed first.", err=True)
            raise typer.Exit(1)
        conn.execute(
            "INSERT INTO decisions (entity_type, entity_id, actor_id, kind, reason, old_value, new_value, pending_approval) VALUES ('project', ?, ?, 'status_change', ?, ?, 'completed', 1)",
            (proj["id"], actor_id, reason, proj["status"] or "active"),
        )
        conn.commit()
        dec_row = conn.execute("SELECT id, entity_type, entity_id, actor_id, kind, reason, pending_approval, created_at FROM decisions WHERE id = last_insert_rowid()").fetchone()
        out = dict(dec_row)
        out["pending_approval"] = bool(out["pending_approval"])
        out["created_at"] = str(out["created_at"])
        emit(out, use_pretty(pretty))
    finally:
        conn.close()
