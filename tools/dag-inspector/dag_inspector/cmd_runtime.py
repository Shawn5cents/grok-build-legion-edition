"""cmd_runtime.py — show the active DAG routing.

Default invocation prints a human-readable summary:

    $ dag-inspector runtime
    Active DAG label: MIXED  (aliases: diverse, multi-family, ...)
    Path: ~/.grok/config-presets/mixed-dag.toml
    Enabled: yes    Default model: deepseek-v4-pro
    Use for: daily work with ...
    Cost: LOW–MEDIUM    Switch: dag mixed

    ROLES
      Role             Primary              Fallback
      orchestrator     deepseek-v4-pro      deepseek-v4-flash
      explore          deepseek-v4-flash    gpt-5.6-luna
      plan             minimax-m3           gpt-5.6-luna
      ...

    MODEL BLOCKS
      Model id           Provider    URL                          Keys (set/missing)
      deepseek-v4-pro    deepseek    api.deepseek.com/v1         DEEPSEEK_API_KEY set
      minimax-m3         minimax    api.minimax.io/v1           MINIMAX_API_KEY set
      qwen3-flash        openrouter openrouter.ai/api/v1         OPENROUTER_API_KEY set
      gpt-5.6-luna       openai     api.openai.com/v1            OPENAI_API_KEY missing

With ``--json`` it emits a single JSON document.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from . import formatting
from .config import Config


def build_runtime_view(cfg: Config) -> Dict[str, Any]:
    """Return a JSON-serializable view of the runtime DAG routing."""
    rows: List[Dict[str, Any]] = []
    for role in cfg.ordered_roles():
        primary = cfg.primaries.get(role, "")
        fallback = cfg.fallbacks.get(role, "")
        primary_block = cfg.models.get(primary)
        fallback_block = cfg.models.get(fallback)
        rows.append(
            {
                "role": role,
                "primary": primary,
                "primary_provider": primary_block.provider() if primary_block else "",
                "primary_base_url": primary_block.base_url if primary_block else "",
                "fallback": fallback,
                "fallback_provider": fallback_block.provider() if fallback_block else "",
                "fallback_base_url": fallback_block.base_url if fallback_block else "",
            }
        )

    model_rows: List[Dict[str, Any]] = []
    for mid, mb in cfg.models.items():
        env_status = []
        for k in mb.env_key:
            env_status.append({"key": k, "set": bool(os.environ.get(k))})
        model_rows.append(
            {
                "id": mid,
                "model": mb.model,
                "name": mb.name,
                "provider": mb.provider(),
                "base_url": mb.base_url,
                "api_backend": mb.api_backend,
                "context_window": mb.context_window,
                "env_key": mb.env_key,
                "env_status": env_status,
            }
        )

    goal = [
        {"role": g.role, "model": g.model, "agent_type": g.agent_type}
        for g in cfg.goal_roles
    ]

    return {
        "path": cfg.path,
        "label": cfg.header.label,
        "aliases": cfg.header.aliases,
        "description": cfg.header.description,
        "use_for": cfg.header.use_for,
        "cost": cfg.header.cost,
        "switch_command": cfg.header.switch,
        "enabled": cfg.enabled,
        "default_model": cfg.default_model,
        "fork_secondary_model": cfg.fork_secondary_model,
        "roles": rows,
        "models": model_rows,
        "goal_roles": goal,
        "missing_env_keys": cfg.env_keys_missing(),
    }


def render_runtime(cfg: Config) -> None:
    """Pretty-print the runtime view to stdout."""
    view = build_runtime_view(cfg)

    # Header block
    print(formatting.header_line(f"DAG label: {view['label']}"))
    aliases = ", ".join(view["aliases"]) if view["aliases"] else "—"
    print(f"  aliases   : {aliases}")
    print(f"  path      : {view['path']}")
    print(f"  enabled   : {'yes' if view['enabled'] else 'no'}")
    print(f"  default   : {view['default_model']}")
    print(f"  use_for   : {view['use_for'] or '—'}")
    print(f"  cost      : {view['cost'] or '—'}")
    print(f"  switch    : {view['switch_command'] or '—'}")
    if view["fork_secondary_model"]:
        print(f"  fork secondary : {view['fork_secondary_model']}")
    if view["description"]:
        print()
        for line in view["description"].splitlines():
            if line.strip():
                print(f"  {formatting.dim(line)}")
    print()

    # ROLES table
    print(formatting.bold("ROLES"))
    rows: List[Tuple[str, str, str, str, str]] = []
    for r in view["roles"]:
        primary_cell = f"{r['primary']}"
        if r["primary_provider"]:
            primary_cell += f" ({r['primary_provider']})"
        fallback_cell = r["fallback"] or "—"
        if r["fallback_provider"]:
            fallback_cell += f" ({r['fallback_provider']})"
        primary_status = _status_for_primary(cfg, r["primary"])
        rows.append(
            (
                r["role"],
                primary_cell,
                fallback_cell,
                primary_status,
                "primary",
            )
        )
    formatting.print_table(("Role", "Primary", "Fallback", "Status", "Origin"), rows)
    print()

    # MODEL BLOCKS
    print(formatting.bold("MODEL BLOCKS"))
    mrows: List[Tuple[str, str, str, str, str]] = []
    for m in view["models"]:
        keys_text = ", ".join(
            f"{es['key']}={'set' if es['set'] else 'MISSING'}" for es in m["env_status"]
        )
        if not keys_text:
            keys_text = "—"
        mrows.append(
            (
                m["id"],
                m["provider"],
                m["api_backend"] or "chat_completions",
                m["base_url"] or "—",
                keys_text,
            )
        )
    formatting.print_table(("Model id", "Provider", "Backend", "Base URL", "Env keys"), mrows)
    print()

    # GOAL DAG
    if view["goal_roles"]:
        print(formatting.bold("GOAL DAG"))
        grows = []
        for g in view["goal_roles"]:
            grows.append((g["role"], g["model"], g["agent_type"]))
        formatting.print_table(("Role", "Model", "Agent type"), grows)
        print()

    # MISSING keys warning
    if view["missing_env_keys"]:
        print(formatting.yellow("MISSING ENV KEYS (fallbacks will fail):"))
        for k in view["missing_env_keys"]:
            print(f"  - {k}")
        print()


def _status_for_primary(cfg: Config, primary_id: str) -> str:
    mb = cfg.models.get(primary_id)
    if not mb:
        return "missing-model"
    missing = [k for k in mb.env_key if not os.environ.get(k)]
    if missing:
        return formatting.yellow("missing-key:" + ",".join(missing))
    return formatting.green("ok")