import json
import sys
from typing import Any


def is_tty() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def use_pretty(pretty_flag: bool | None) -> bool:
    if pretty_flag is not None:
        return pretty_flag
    return is_tty()


def emit(data: Any, pretty: bool) -> None:
    if pretty:
        print(json.dumps(data, indent=2))
    else:
        print(json.dumps(data))


def emit_pretty_text(lines: list[str]) -> None:
    for line in lines:
        print(line)
