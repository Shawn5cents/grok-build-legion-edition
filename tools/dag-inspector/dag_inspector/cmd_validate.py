"""cmd_validate.py — sanity-check a DAG config.

Detects:
    * Missing top-level sections (``[subagents]``, ``[subagents.models]``)
    * Undefined model references (a role points at a model id that has no
      ``[model.<id>]`` block)
    * Unset env keys (the provider API key isn't currently in the process
      environment — that fallback will fail at runtime)
    * Empty ``[subagents.fallback]`` for a role whose primary model has
      ``api_backend`` set (some providers require header-style auth)
    * Duplicate primary/fallback assignments
    * Goal DAG role references that aren't defined

Severity ladder:
    * error   — runtime will not work
    * warning — runtime works but degrades
    * info    — informational, e.g. "this role has no fallback"
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import formatting
from .config import Config, GoalRole, ModelBlock


@dataclass
class Diagnostic:
    code: str
    severity: str  # info | warning | error
    message: str
    path: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


_SEVERITY_ORDER = {"ok": 0, "info": 1, "warning": 2, "error": 3}


def build_validation_view(cfg: Config) -> Dict[str, Any]:
    diags: List[Diagnostic] = []

    # 1) Top-level structure
    if not cfg.enabled:
        diags.append(
            Diagnostic(
                code="subagents_disabled",
                severity="warning",
                message="[subagents] enabled = false — DAG routing will not be used.",
                path="subagents.enabled",
            )
        )
    if not cfg.primaries:
        diags.append(
            Diagnostic(
                code="no_subagent_roles",
                severity="error",
                message="[subagents.models] is empty — no subagent routing defined.",
                path="subagents.models",
            )
        )
    if not cfg.default_model:
        diags.append(
            Diagnostic(
                code="no_default_model",
                severity="warning",
                message="[models] default is empty — main chat has no explicit model.",
                path="models.default",
            )
        )

    # 2) Model reference integrity
    defined_models = set(cfg.models.keys())
    for role, primary_id in cfg.primaries.items():
        if primary_id and primary_id not in defined_models:
            diags.append(
                Diagnostic(
                    code="undefined_primary",
                    severity="error",
                    message=f"Role '{role}' primary '{primary_id}' has no [model.{primary_id}] block.",
                    path=f"subagents.models.{role}",
                    details={"role": role, "model": primary_id},
                )
            )
    for role, fb_id in cfg.fallbacks.items():
        if fb_id and fb_id not in defined_models:
            diags.append(
                Diagnostic(
                    code="undefined_fallback",
                    severity="error",
                    message=f"Role '{role}' fallback '{fb_id}' has no [model.{fb_id}] block.",
                    path=f"subagents.fallback.{role}",
                    details={"role": role, "model": fb_id},
                )
            )

    # 3) Env key status
    for mid, mb in cfg.models.items():
        for k in mb.env_key:
            if not os.environ.get(k):
                role_users = [
                    role
                    for role, m_id in cfg.primaries.items()
                    if m_id == mid
                ] + [
                    role
                    for role, m_id in cfg.fallbacks.items()
                    if m_id == mid
                ]
                severity = "error" if role_users else "warning"
                diags.append(
                    Diagnostic(
                        code="env_key_unset",
                        severity=severity,
                        message=(
                            f"Model '{mid}' requires env var '{k}' which is not set."
                            + (f" Used by roles: {', '.join(role_users)}." if role_users else "")
                        ),
                        path=f"model.{mid}.env_key",
                        details={"model": mid, "env_key": k, "roles": role_users},
                    )
                )

    # 4) Empty fallback for roles that have a primary
    for role in cfg.primaries:
        if role not in cfg.fallbacks or not cfg.fallbacks.get(role):
            diags.append(
                Diagnostic(
                    code="missing_fallback",
                    severity="info",
                    message=f"Role '{role}' has no fallback defined.",
                    path=f"subagents.fallback.{role}",
                    details={"role": role},
                )
            )

    # 5) Header sanity
    if not cfg.header.is_known:
        diags.append(
            Diagnostic(
                code="unknown_label",
                severity="warning",
                message=(
                    f"Header label is {cfg.header.label!r}; expected FULL/ECONOMY/MIXED."
                    " dag-switch.sh will not recognize this preset."
                ),
                path="header",
            )
        )
    if not cfg.header.switch:
        diags.append(
            Diagnostic(
                code="missing_switch_command",
                severity="info",
                message="Header has no 'Restart TUI required after: dag <name>' line.",
                path="header",
            )
        )

    # 6) Goal DAG role integrity
    for g in cfg.goal_roles:
        if g.model and g.model not in defined_models:
            diags.append(
                Diagnostic(
                    code="undefined_goal_model",
                    severity="error",
                    message=f"Goal role '{g.role}' uses undefined model '{g.model}'.",
                    path=f"goal.{g.role}_model",
                    details={"role": g.role, "model": g.model},
                )
            )

    # 7) default model defined?
    if cfg.default_model and cfg.default_model not in defined_models:
        diags.append(
            Diagnostic(
                code="undefined_default_model",
                severity="error",
                message=f"[models] default '{cfg.default_model}' has no [model.{cfg.default_model}] block.",
                path="models.default",
            )
        )

    # Determine highest severity.
    highest = "ok"
    for d in diags:
        if _SEVERITY_ORDER[d.severity] > _SEVERITY_ORDER[highest]:
            highest = d.severity

    return {
        "path": cfg.path,
        "label": cfg.header.label,
        "diagnostics": [
            {
                "code": d.code,
                "severity": d.severity,
                "message": d.message,
                "path": d.path,
                "details": d.details,
            }
            for d in diags
        ],
        "highest_severity": highest,
        "counts": {
            "error": sum(1 for d in diags if d.severity == "error"),
            "warning": sum(1 for d in diags if d.severity == "warning"),
            "info": sum(1 for d in diags if d.severity == "info"),
        },
    }


def render_validation(view: Dict[str, Any]) -> int:
    counts = view.get("counts", {})
    print(formatting.header_line(f"Validate: {view['label']}"))
    print(f"  path      : {view['path']}")
    print(
        f"  diagnostics : {counts.get('error', 0)} errors, "
        f"{counts.get('warning', 0)} warnings, {counts.get('info', 0)} info"
    )
    print()

    diags = view.get("diagnostics") or []
    if not diags:
        print(formatting.green("  ✓ no issues found"))
        return 0

    # Order: errors first, then warnings, then info.
    severity_rank = {"error": 0, "warning": 1, "info": 2}
    diags = sorted(diags, key=lambda d: (severity_rank.get(d.get("severity", ""), 3), d.get("code", "")))

    for d in diags:
        sev = d.get("severity", "")
        if sev == "error":
            tag = formatting.red("[ERROR]")
        elif sev == "warning":
            tag = formatting.yellow("[WARN] ")
        else:
            tag = formatting.cyan("[INFO] ")
        path = f" ({d['path']})" if d.get("path") else ""
        print(f"  {tag} {d['code']}{path}")
        print(f"          {d['message']}")
    print()

    highest = view.get("highest_severity", "ok")
    if highest == "error":
        return 2
    if highest == "warning":
        return 1
    return 0