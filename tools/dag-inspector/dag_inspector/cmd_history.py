"""cmd_history.py — walk config.toml.bak-* files for switch timeline.

Lists backups newest → oldest, parsing the DAG header from each so we can
show label transitions across the timeline.

Filenames follow two patterns:

1. ``config.toml.bak-YYYYMMDD-HHMMSS``           — automatic snapshot
2. ``config.toml.bak-dag-<label>-YYYYMMDD-HHMMSS`` — dag-switch.sh backup

We accept both and any other variant (``-pre-xai``, ``-configB``, etc.).
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import formatting, paths
from .config import load_file
from .header import parse_header_from_file


_TS_RE = re.compile(r"(\d{8})[_-]?(\d{6})")
_LABEL_RE = re.compile(r"bak-(?:dag-)?([a-zA-Z]+)", re.IGNORECASE)


def _parse_backup_ts(name: str) -> Optional[datetime]:
    """Pull a timestamp out of a backup filename if present."""
    m = _TS_RE.search(name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def _backup_label_hint(name: str) -> str:
    """Pull ``full`` / ``economy`` / ``mixed`` hint out of ``bak-dag-full-...``."""
    m = _LABEL_RE.search(name)
    return m.group(1).lower() if m else ""


def build_history_view(
    home: str = None,
    limit: int = 20,
    backup_glob: List[str] = None,
) -> Dict[str, Any]:
    home = home or paths.grok_home()
    files = backup_glob if backup_glob is not None else paths.backup_glob(home)

    entries: List[Dict[str, Any]] = []
    for path in files:
        try:
            header = parse_header_from_file(path)
            cfg = load_file(path)
        except (OSError, ValueError):
            header = None
            cfg = None

        ts = _parse_backup_ts(os.path.basename(path))
        hint = _backup_label_hint(os.path.basename(path))
        entries.append(
            {
                "path": path,
                "filename": os.path.basename(path),
                "timestamp": ts.isoformat() if ts else "",
                "label": (header.label if header else "") or hint.upper() or "unknown",
                "default_model": cfg.default_model if cfg else "",
                "enabled": cfg.enabled if cfg else False,
                "size": os.path.getsize(path) if os.path.exists(path) else 0,
            }
        )

    # Detect label transitions — walk oldest → newest so the "from → to"
    # direction is correct.
    transitions: List[Dict[str, Any]] = []
    chronological = sorted(entries, key=lambda e: e["timestamp"] or "")
    prev_label = ""
    for e in chronological:
        cur = e["label"]
        if cur and cur != prev_label and cur != "unknown":
            transitions.append(
                {
                    "timestamp": e["timestamp"],
                    "label": cur,
                    "filename": e["filename"],
                    "from": prev_label or "(start)",
                    "to": cur,
                }
            )
            prev_label = cur
    # Present newest → oldest for the user.
    transitions.reverse()

    if limit and len(entries) > limit:
        entries = entries[:limit]

    return {
        "grok_home": home,
        "total_backups": len(files),
        "shown": len(entries),
        "transitions": transitions,
        "entries": entries,
    }


def render_history(view: Dict[str, Any]) -> None:
    print(formatting.header_line("Config backup history"))
    print(f"  grok_home    : {view['grok_home']}")
    print(f"  total backups: {view['total_backups']}")
    print(f"  shown        : {view['shown']}")
    print()

    if view["transitions"]:
        print(formatting.bold("LABEL TRANSITIONS (newest → oldest)"))
        rows = []
        for t in view["transitions"]:
            rows.append(
                (
                    t["timestamp"],
                    t["from"] + " → " + t["to"],
                    t["filename"],
                )
            )
        formatting.print_table(("Timestamp", "Transition", "File"), rows)
        print()

    if view["entries"]:
        print(formatting.bold("BACKUPS (newest first)"))
        rows = []
        for e in view["entries"]:
            rows.append(
                (
                    e["timestamp"] or "—",
                    e["label"],
                    e["default_model"] or "—",
                    "yes" if e["enabled"] else "no",
                    str(e["size"]),
                    e["filename"],
                )
            )
        formatting.print_table(
            ("Timestamp", "Label", "Default", "Enabled", "Size", "Filename"), rows
        )
    else:
        print(formatting.dim("  (no backups found)"))