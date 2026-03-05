import typer
from pm.db import get_connection

app = typer.Typer()


@app.command()
def init_cmd(
    human: str | None = typer.Option(None, "--human", help="Create an initial human actor (optional, for scripting)."),
    agent: list[str] = typer.Option(default=[], "--agent", help="Create an initial agent actor (optional, repeatable)."),
) -> None:
    """Ensure DB is initialized; optionally create initial human/agent(s) with --human and --agent. DB is created automatically on first use of any pm command."""
    conn = get_connection()
    try:
        if human:
            conn.execute("INSERT OR IGNORE INTO actors (name, role) VALUES (?, ?)", (human, "human"))
        for name in agent:
            conn.execute("INSERT OR IGNORE INTO actors (name, role) VALUES (?, ?)", (name, "agent"))
        if human or agent:
            conn.commit()
        typer.echo("Initialized.")
    finally:
        conn.close()
