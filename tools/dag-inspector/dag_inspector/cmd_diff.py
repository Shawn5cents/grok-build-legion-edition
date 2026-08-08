"""cmd_diff.py — compare two DAG configs.

Reports:

* Default-model change
* Per-role primary / fallback changes (added / removed / changed)
* Per-model-block changes (URL, env_key, context_window, api_backend)
* Models added / removed entirely
* Goal DAG role changes

The output is stable: section ordering is fixed so two runs of the same diff
produce the same output (good for piping into ``diff`` / git).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from . import formatting
from .config import Config


CHANGE_KIND_ADD = "added"
CHANGE_KIND_REMOVE = "removed"
CHANGE_KIND_CHANGE = "changed"


@dataclass
class _Change:
    kind: str  # added | removed | changed
    path: str
    before: Any = None
    after: Any = None


def _coerce(v: Any) -> Any:
    """Normalize values so dict comparisons are stable."""
    if isinstance(v, list):
        return sorted([_coerce(x) for x in v])
    if isinstance(v, dict):
        return {k: _coerce(v[k]) for k in sorted(v.keys())}
    return v


def build_diff_view(a: Config, b: Config) -> Dict[str, Any]:
    changes: List[_Change] = []

    # Default model
    if a.default_model != b.default_model:
        changes.append(
            _Change(
                CHANGE_KIND_CHANGE,
                "[models].default",
                before=a.default_model or None,
                after=b.default_model or None,
            )
        )

    # Header / label
    if a.header.label != b.header.label:
        changes.append(
            _Change(
                CHANGE_KIND_CHANGE,
                "header.label",
                before=a.header.label,
                after=b.header.label,
            )
        )

    # Primaries
    a_roles = set(a.primaries.keys())
    b_roles = set(b.primaries.keys())
    for role in sorted(a_roles - b_roles):
        changes.append(
            _Change(
                CHANGE_KIND_REMOVE,
                f"subagents.models.{role}",
                before=a.primaries[role],
                after=None,
            )
        )
    for role in sorted(b_roles - a_roles):
        changes.append(
            _Change(
                CHANGE_KIND_ADD,
                f"subagents.models.{role}",
                before=None,
                after=b.primaries[role],
            )
        )
    for role in sorted(a_roles & b_roles):
        if a.primaries[role] != b.primaries[role]:
            changes.append(
                _Change(
                    CHANGE_KIND_CHANGE,
                    f"subagents.models.{role}",
                    before=a.primaries[role],
                    after=b.primaries[role],
                )
            )

    # Fallbacks
    a_fb = set(a.fallbacks.keys())
    b_fb = set(b.fallbacks.keys())
    for role in sorted(a_fb - b_fb):
        changes.append(
            _Change(
                CHANGE_KIND_REMOVE,
                f"subagents.fallback.{role}",
                before=a.fallbacks[role],
                after=None,
            )
        )
    for role in sorted(b_fb - a_fb):
        changes.append(
            _Change(
                CHANGE_KIND_ADD,
                f"subagents.fallback.{role}",
                before=None,
                after=b.fallbacks[role],
            )
        )
    for role in sorted(a_fb & b_fb):
        if a.fallbacks[role] != b.fallbacks[role]:
            changes.append(
                _Change(
                    CHANGE_KIND_CHANGE,
                    f"subagents.fallback.{role}",
                    before=a.fallbacks[role],
                    after=b.fallbacks[role],
                )
            )

    # Model blocks
    a_models = set(a.models.keys())
    b_models = set(b.models.keys())
    for mid in sorted(a_models - b_models):
        changes.append(_Change(CHANGE_KIND_REMOVE, f"model.{mid}"))
    for mid in sorted(b_models - a_models):
        changes.append(_Change(CHANGE_KIND_ADD, f"model.{mid}"))
    for mid in sorted(a_models & b_models):
        ma = a.models[mid]
        mb = b.models[mid]
        for field in ("base_url", "api_backend", "context_window"):
            va = getattr(ma, field)
            vb = getattr(mb, field)
            if va != vb:
                changes.append(
                    _Change(
                        CHANGE_KIND_CHANGE,
                        f"model.{mid}.{field}",
                        before=va,
                        after=vb,
                    )
                )
        if sorted(ma.env_key) != sorted(mb.env_key):
            changes.append(
                _Change(
                    CHANGE_KIND_CHANGE,
                    f"model.{mid}.env_key",
                    before=sorted(ma.env_key),
                    after=sorted(mb.env_key),
                )
            )

    # Goal roles
    a_goal = {(g.role, g.model): g for g in a.goal_roles}
    b_goal = {(g.role, g.model): g for g in b.goal_roles}
    a_keys = set(a_goal.keys())
    b_keys = set(b_goal.keys())
    for key in sorted(a_keys - b_keys):
        changes.append(
            _Change(
                CHANGE_KIND_REMOVE,
                f"goal.{key[0]}",
                before=key[1],
                after=None,
            )
        )
    for key in sorted(b_keys - a_keys):
        changes.append(
            _Change(
                CHANGE_KIND_ADD,
                f"goal.{key[0]}",
                before=None,
                after=key[1],
            )
        )

    # Summary
    counts = {
        CHANGE_KIND_ADD: sum(1 for c in changes if c.kind == CHANGE_KIND_ADD),
        CHANGE_KIND_REMOVE: sum(1 for c in changes if c.kind == CHANGE_KIND_REMOVE),
        CHANGE_KIND_CHANGE: sum(1 for c in changes if c.kind == CHANGE_KIND_CHANGE),
    }

    return {
        "source": {
            "path": a.path,
            "label": a.header.label,
        },
        "target": {
            "path": b.path,
            "label": b.header.label,
        },
        "counts": counts,
        "changes": [
            {"kind": c.kind, "path": c.path, "before": c.before, "after": c.after}
            for c in changes
        ],
    }


def render_diff(a: Config, b: Config) -> None:
    view = build_diff_view(a, b)
    print(formatting.header_line("Diff"))
    print(f"  source : {view['source']['label']}  ({view['source']['path']})")
    print(f"  target : {view['target']['label']}  ({view['target']['path']})")
    counts = view["counts"]
    print(
        f"  changes: +{counts['added']} -{counts['removed']} ~{counts['changed']}"
    )
    print()
    if not view["changes"]:
        print(formatting.green("  ✓ no differences"))
        return

    # Section by kind for readability.
    for kind, label in (
        (CHANGE_KIND_ADD, "ADDED"),
        (CHANGE_KIND_REMOVE, "REMOVED"),
        (CHANGE_KIND_CHANGE, "CHANGED"),
    ):
        rows = [
            (c["path"], "" if c["before"] is None else str(c["before"]),
             "" if c["after"] is None else str(c["after"]))
            for c in view["changes"]
            if c["kind"] == kind
        ]
        if not rows:
            continue
        print(formatting.bold(label))
        formatting.print_table(("Path", "Before", "After"), rows)
        print()