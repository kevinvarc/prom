import typer
from pm.commands import actor, alerts, decide, init, project, review, status, subproject, task, idea

app = typer.Typer()

app.command("init")(init.init_cmd)

app.add_typer(actor.app, name="actor")

app.add_typer(project.app, name="project")

app.add_typer(subproject.app, name="subproject")

app.add_typer(task.app, name="task")

app.add_typer(idea.app, name="idea")

app.add_typer(decide.app, name="decide")

app.command("status")(status.status_cmd)

app.command("alerts")(alerts.alerts_cmd)

app.command("review")(review.review_cmd)
