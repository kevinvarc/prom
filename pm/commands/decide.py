import typer
from pm.db import get_connection
from pm.output import emit, use_pretty
from pm.utils import get_actor_id

app = typer.Typer()


@app.command("pending")
def pending_cmd(pretty: bool = typer.Option(None, "--pretty")) -> None:
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT id, entity_type, entity_id, actor_id, at, kind, reason, old_value, new_value, created_at FROM decisions WHERE pending_approval = 1 ORDER BY created_at"
        )
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r["at"] = str(r["at"])
            r["created_at"] = str(r["created_at"])
        emit(rows, use_pretty(pretty))
    finally:
        conn.close()


@app.command("approve")
def approve_cmd(
    decision_id: int = typer.Argument(...),
    actor: str = typer.Option(..., "--actor"),
    pretty: bool = typer.Option(None, "--pretty"),
) -> None:
    conn = get_connection()
    try:
        actor_id = get_actor_id(conn, actor)
        if not actor_id:
            typer.echo(f"Unknown actor: {actor}", err=True)
            raise typer.Exit(1)
        cur = conn.execute(
            "SELECT id, entity_type, entity_id, kind, new_value, pending_approval FROM decisions WHERE id = ?",
            (decision_id,),
        )
        row = cur.fetchone()
        if not row:
            typer.echo("Decision not found.", err=True)
            raise typer.Exit(1)
        dec = dict(row)
        if not dec["pending_approval"]:
            typer.echo("Decision is not pending approval.", err=True)
            raise typer.Exit(1)
        conn.execute(
            "UPDATE decisions SET pending_approval = 0, approved_by_actor_id = ?, approved_at = datetime('now') WHERE id = ?",
            (actor_id, decision_id),
        )
        if dec["entity_type"] == "project":
            if dec["kind"] == "purpose_change" and dec["new_value"]:
                conn.execute(
                    "UPDATE projects SET purpose = ?, updated_at = datetime('now') WHERE id = ?",
                    (dec["new_value"], dec["entity_id"]),
                )
            elif dec["kind"] == "status_change" and dec["new_value"] == "completed":
                conn.execute(
                    "UPDATE projects SET status = 'completed', updated_at = datetime('now') WHERE id = ?",
                    (dec["entity_id"],),
                )
        conn.commit()
        row = conn.execute(
            "SELECT id, entity_type, entity_id, actor_id, kind, reason, pending_approval, approved_by_actor_id, approved_at, created_at FROM decisions WHERE id = ?",
            (decision_id,),
        ).fetchone()
        out = dict(row)
        out["pending_approval"] = bool(out["pending_approval"])
        out["created_at"] = str(out["created_at"])
        if out.get("approved_at"):
            out["approved_at"] = str(out["approved_at"])
        emit(out, use_pretty(pretty))
    finally:
        conn.close()


@app.command("reject")
def reject_cmd(
    decision_id: int = typer.Argument(...),
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
        cur = conn.execute("SELECT id, entity_type, entity_id, pending_approval FROM decisions WHERE id = ?", (decision_id,))
        row = cur.fetchone()
        if not row:
            typer.echo("Decision not found.", err=True)
            raise typer.Exit(1)
        dec = dict(row)
        if not dec["pending_approval"]:
            typer.echo("Decision is not pending approval.", err=True)
            raise typer.Exit(1)
        conn.execute("UPDATE decisions SET pending_approval = 0 WHERE id = ?", (decision_id,))
        conn.execute(
            "INSERT INTO decisions (entity_type, entity_id, actor_id, kind, reason, pending_approval) VALUES (?, ?, ?, 'other', ?, 0)",
            (dec["entity_type"], dec["entity_id"], actor_id, "Rejected: " + reason),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, entity_type, entity_id, actor_id, kind, reason, pending_approval, created_at FROM decisions WHERE id = ?",
            (decision_id,),
        ).fetchone()
        out = dict(row)
        out["pending_approval"] = bool(out["pending_approval"])
        out["created_at"] = str(out["created_at"])
        emit(out, use_pretty(pretty))
    finally:
        conn.close()
