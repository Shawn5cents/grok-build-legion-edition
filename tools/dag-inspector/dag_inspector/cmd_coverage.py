"""cmd_coverage.py — runtime coverage from unified.jsonl.

Walks subagent spawn events in the lookback window and reports:

* Per-role spawn counts
* Per-model spawn counts
* Coverage matrix (role × primary model)
* Outcome breakdown (completed / failed / cancelled)
* Gaps — configured roles / models that never appeared in the window

Useful answers:

    "Has the verifier role actually been used in the last 24h?"
    "Did we ever fall back to gpt-5.6-luna?"
    "Are any configured primaries never spawned?"
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Tuple

from . import formatting, paths
from .config import Config
from .log_reader import SpawnEvent, TerminalEvent, read_all


def build_coverage_view(
    cfg: Config,
    lookback_min: int = 1440,
    log_path: str = None,
) -> Dict[str, Any]:
    log_path = log_path or paths.log_file()
    spawns, terminals, _malformed, total_lines = read_all(
        log_path, lookback_min=lookback_min
    )

    # Per-role counts (spawn + terminal outcomes)
    role_spawns: Counter = Counter(s.role for s in spawns if s.role)
    role_outcomes: Dict[str, Counter] = {}
    for t in terminals:
        if not t.role:
            continue
        rc = role_outcomes.setdefault(t.role, Counter())
        rc[t.outcome] += 1

    # Per-model counts
    model_spawns: Counter = Counter(s.model for s in spawns if s.model)
    model_outcomes: Dict[str, Counter] = {}
    for t in terminals:
        if not t.model:
            continue
        mc = model_outcomes.setdefault(t.model, Counter())
        mc[t.outcome] += 1

    # Coverage matrix — role × model
    matrix: Dict[Tuple[str, str], int] = {}
    for s in spawns:
        if not s.role or not s.model:
            continue
        key = (s.role, s.model)
        matrix[key] = matrix.get(key, 0) + 1

    # Time range
    if spawns:
        first_ts = min(s.ts for s in spawns)
        last_ts = max(s.ts for s in spawns)
    else:
        first_ts = ""
        last_ts = ""

    # Gaps
    configured_roles = set(cfg.ordered_roles())
    used_roles = {s.role for s in spawns if s.role}
    unspawned_roles = sorted(configured_roles - used_roles)

    configured_primaries = {m for m in cfg.primaries.values() if m}
    configured_fallbacks = {m for m in cfg.fallbacks.values() if m}
    configured_models = set(cfg.models.keys())
    used_models = {s.model for s in spawns if s.model}
    unused_models = sorted(
        (configured_models | configured_primaries | configured_fallbacks) - used_models
    )

    return {
        "lookback_min": lookback_min,
        "log_path": log_path,
        "log_total_lines": total_lines,
        "config_label": cfg.header.label,
        "first_event_ts": first_ts,
        "last_event_ts": last_ts,
        "totals": {
            "spawns": len(spawns),
            "terminals": len(terminals),
        },
        "role_spawns": dict(role_spawns),
        "role_outcomes": {k: dict(v) for k, v in role_outcomes.items()},
        "model_spawns": dict(model_spawns),
        "model_outcomes": {k: dict(v) for k, v in model_outcomes.items()},
        "matrix": [
            {"role": r, "model": m, "count": c}
            for (r, m), c in sorted(matrix.items())
        ],
        "gaps": {
            "unspawned_roles": unspawned_roles,
            "unused_models": unused_models,
        },
        "outcome_totals": {
            "completed": sum(t.outcome == "completed" for t in terminals),
            "failed": sum(t.outcome == "failed" for t in terminals),
            "cancelled": sum(t.outcome == "cancelled" for t in terminals),
        },
    }


def render_coverage(view: Dict[str, Any]) -> None:
    print(formatting.header_line(f"Coverage: {view.get('config_label', '?')}"))
    print(f"  lookback   : {view['lookback_min']} min")
    print(f"  log        : {view['log_path']}")
    print(f"  log lines  : {view['log_total_lines']}")
    print(f"  first event: {view['first_event_ts'] or '—'}")
    print(f"  last event : {view['last_event_ts'] or '—'}")
    totals = view["totals"]
    print(f"  spawns     : {totals['spawns']}")
    print(f"  terminals  : {totals['terminals']}")
    oc = view["outcome_totals"]
    print(
        f"  outcomes   : {oc['completed']} completed, "
        f"{oc['failed']} failed, {oc['cancelled']} cancelled"
    )
    print()

    # Per-role table
    if view["role_spawns"]:
        print(formatting.bold("PER-ROLE"))
        rs = view["role_spawns"]
        ro = view["role_outcomes"]
        all_roles = sorted(set(rs.keys()) | set(ro.keys()))
        rows = []
        for r in all_roles:
            o = ro.get(r, {})
            rows.append(
                (
                    r,
                    rs.get(r, 0),
                    o.get("completed", 0),
                    o.get("failed", 0),
                    o.get("cancelled", 0),
                )
            )
        formatting.print_table(
            ("Role", "Spawns", "Completed", "Failed", "Cancelled"), rows
        )
        print()

    # Per-model table
    if view["model_spawns"]:
        print(formatting.bold("PER-MODEL"))
        ms = view["model_spawns"]
        mo = view["model_outcomes"]
        all_models = sorted(set(ms.keys()) | set(mo.keys()))
        rows = []
        for m in all_models:
            o = mo.get(m, {})
            rows.append(
                (
                    m,
                    ms.get(m, 0),
                    o.get("completed", 0),
                    o.get("failed", 0),
                    o.get("cancelled", 0),
                )
            )
        formatting.print_table(
            ("Model", "Spawns", "Completed", "Failed", "Cancelled"), rows
        )
        print()

    # Coverage matrix
    if view["matrix"]:
        print(formatting.bold("ROLE × MODEL MATRIX"))
        rows = [(c["role"], c["model"], c["count"]) for c in view["matrix"]]
        formatting.print_table(("Role", "Model", "Spawns"), rows)
        print()

    # Gaps
    gaps = view["gaps"]
    has_gap = False
    if gaps["unspawned_roles"]:
        has_gap = True
        print(formatting.yellow("UNSPAWNED ROLES (configured but never ran):"))
        for r in gaps["unspawned_roles"]:
            print(f"  - {r}")
        print()
    if gaps["unused_models"]:
        has_gap = True
        print(formatting.yellow("UNUSED MODELS (defined but never spawned):"))
        for m in gaps["unused_models"]:
            print(f"  - {m}")
        print()
    if not has_gap:
        print(formatting.green("  ✓ no coverage gaps"))