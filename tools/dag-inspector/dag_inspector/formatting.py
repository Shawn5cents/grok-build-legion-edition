"""formatting.py — JSON + table + color helpers for dag-inspector output.

Keeps the presentation layer out of the command modules. JSON serialization
is dataclass-aware so ``--json`` always works for callers, even though the
default rendering uses ASCII tables with ANSI color.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
from typing import Any, Dict, List, Sequence


# ---------------------------------------------------------------------------
# Color
# ---------------------------------------------------------------------------


_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
_FORCE_COLOR = os.environ.get("DAG_INSPECTOR_COLOR") == "1"


def color_enabled() -> bool:
    return _USE_COLOR or _FORCE_COLOR


def color(code: str, text: str) -> str:
    """Wrap ``text`` in ANSI escapes if colors are enabled.

    ``code`` is a semicolon-joined ANSI SGR sequence body, e.g. ``"31"`` for
    red, ``"1;33"`` for bold yellow.
    """
    if not color_enabled():
        return text
    return f"\033[{code}m{text}\033[0m"


def red(text: str) -> str:
    return color("31", text)


def green(text: str) -> str:
    return color("32", text)


def yellow(text: str) -> str:
    return color("33", text)


def blue(text: str) -> str:
    return color("34", text)


def cyan(text: str) -> str:
    return color("36", text)


def bold(text: str) -> str:
    return color("1", text)


def dim(text: str) -> str:
    return color("2", text)


# ---------------------------------------------------------------------------
# Dataclass-aware JSON serialization
# ---------------------------------------------------------------------------


def _to_jsonable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return {k: _to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def to_json(obj: Any, indent: int = 2) -> str:
    """Return ``obj`` as a JSON string. Handles dataclasses + nested dicts."""
    return json.dumps(_to_jsonable(obj), indent=indent, sort_keys=False)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def print_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    """Print a simple ASCII table to stdout. Widths follow header widths.

    Cells may be any ``str()``-able type; ``None`` becomes an empty cell.
    """
    str_headers = [str(h) for h in headers]
    str_rows = [["" if c is None else str(c) for c in row] for row in rows]

    widths = [len(h) for h in str_headers]
    for row in str_rows:
        for i, cell in enumerate(row):
            if i >= len(widths):
                widths.append(len(cell))
            elif len(cell) > widths[i]:
                widths[i] = len(cell)

    def fmt_row(cells: Sequence[str]) -> str:
        return "  ".join(c.ljust(widths[i]) for i, c in enumerate(cells))

    sep = "  ".join("-" * w for w in widths)
    print(fmt_row(str_headers))
    print(sep)
    for row in str_rows:
        print(fmt_row(row))


def header_line(title: str) -> str:
    """Render a section heading (bold)."""
    return bold(title)


def kv_table(rows: Sequence[tuple]) -> None:
    """Print a key/value list aligned on ``:`` for compact diagnostic blocks."""
    if not rows:
        return
    width = max(len(str(k)) for k, _ in rows)
    for k, v in rows:
        print(f"  {str(k).ljust(width)} : {v}")