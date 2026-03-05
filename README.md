# pm-cli

A project brain for an AI teammate. SQLite is the source of truth. The agent manages ~90% of operations; the human reviews, approves, and unblocks. Success means you can answer "where we are, how we got here, and what's waiting on me or the agent" without maintaining a manual system.

Output: JSON by default / when not TTY; --pretty when TTY or flag passed

Scheduling: Tool defines what can be known; heartbeat/cron defines when

Brevity: Simple over complex; short lists; no "Next 3 Actions"

Hierarchy
Three levels, hard ceiling — no exceptions:

text
Project (L1)     → the ultimate vision and core goal
  Subproject (L2) → a granular section of work; completion drives project completion
    Task (L3)      → atomic action; tasks drive subproject completion
Task is the atomic floor. No subtasks ever.

A project can have multiple subprojects running in parallel.

A subproject can have multiple tasks, some parallel, some sequential — agent manages order.

All tasks done → subproject can be marked complete (requires decision log + confirmation).

All subprojects done → project can be marked complete (requires decision log + human approval).

Each level has its own health, staleness, and waiting state independently.

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
