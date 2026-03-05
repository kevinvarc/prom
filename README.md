# pm-cli

Project brain CLI for AI-human collaboration. SQLite is the source of truth; the agent manages most operations; the human reviews, approves, and unblocks.

## Install

```bash
pip install -e .
```

## First time

The database is created automatically the first time you run any `pm` command. If you run in a terminal (TTY), you will be prompted once for **Your name (human):** and **Your agent name:**; those are created as actors. No need to run `pm init` unless you want to.

For non-interactive or scripted setup (e.g. no TTY):

```bash
pm init --human "YourName" --agent "AgentName"
```

You can add more actors anytime with `pm actor add <name> --role human|agent`.

## Usage

Add a project (required: slug, name, purpose, actor):

```bash
pm project add my-app --name "My App" --purpose "Ship the product." --actor Stan
```

List projects, get full state, update summary or propose purpose change, complete (with approval):

```bash
pm project list
pm project get my-app
pm project update my-app --summary "In progress."
pm project complete my-app --reason "Done." --actor Kevin
```

Subprojects and tasks:

```bash
pm subproject add my-app "Backend"
pm subproject list my-app
pm task add my-app backend "Implement API"
pm task list my-app backend
pm task start 1 --actor Stan
pm task done 1 --actor Stan
```

Ideas and promote to subproject:

```bash
pm idea add my-app "New feature X"
pm idea promote 2 --actor Stan
```

Decisions (pending, approve, reject):

```bash
pm decide pending
pm decide approve 1 --actor Kevin
pm decide reject 1 --reason "Not now." --actor Kevin
```

Status, alerts, review (for heartbeat/cron):

```bash
pm status my-app
pm alerts
pm review
```

Output is JSON by default; use `--pretty` for indented JSON (or when running in a TTY).

## Config

Database path: `PM_DB` or `~/.pm/projects.db`. Config keys (in DB): `days_yellow_subproject`, `days_red_subproject`, `days_waiting_warn`, `days_waiting_decision`.
