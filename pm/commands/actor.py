import typer
from pm.db import get_connection
from pm.output import emit, use_pretty

app = typer.Typer()


@app.command("add")
def add_cmd(name: str, role: str = typer.Option(..., "--role"), pretty: bool = typer.Option(None, "--pretty")) -> None:
    if role not in ("human", "agent"):
        typer.echo("Role must be human or agent.", err=True)
        raise typer.Exit(1)
    conn = get_connection()
    try:
        conn.execute("INSERT INTO actors (name, role) VALUES (?, ?)", (name, role))
        conn.commit()
        row = conn.execute("SELECT id, name, role, created_at FROM actors WHERE id = last_insert_rowid()").fetchone()
        out = dict(row)
        out["created_at"] = str(out["created_at"])
        emit(out, use_pretty(pretty))
    except Exception as e:
        if "UNIQUE" in str(e):
            typer.echo(f"Actor '{name}' already exists.", err=True)
        else:
            raise
        raise typer.Exit(1)
    finally:
        conn.close()
