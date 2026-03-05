from datetime import datetime, timedelta
from typing import Literal

Health = Literal["green", "yellow", "red"]


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def subproject_health(
    last_task_movement_at: str | None,
    waiting: bool,
    has_open_or_in_progress: bool,
    days_yellow: int,
    days_red: int,
    now: datetime | None = None,
) -> Health:
    if waiting:
        return "green"
    now = now or datetime.utcnow()
    movement = _parse_iso(last_task_movement_at) if last_task_movement_at else None
    if has_open_or_in_progress and movement:
        delta_days = (now - movement).days
        if delta_days < days_yellow:
            return "green"
        if delta_days < days_red:
            return "yellow"
        return "red"
    if movement:
        delta_days = (now - movement).days
        if delta_days < days_yellow:
            return "green"
        if delta_days < days_red:
            return "yellow"
        return "red"
    return "yellow"


def project_health(subproject_healths: list[Health], active_only: bool = True) -> Health:
    if not subproject_healths:
        return "green"
    if "red" in subproject_healths:
        return "red"
    if "yellow" in subproject_healths:
        return "yellow"
    return "green"


def waiting_escalation(
    waiting_updated_at: str | None,
    days_warn: int,
    days_decision: int,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.utcnow()
    if not waiting_updated_at:
        return {"warn": False, "require_decision": False}
    t = _parse_iso(waiting_updated_at)
    if not t:
        return {"warn": False, "require_decision": False}
    delta_days = (now - t).days
    return {
        "warn": delta_days >= days_warn,
        "require_decision": delta_days >= days_decision,
    }
