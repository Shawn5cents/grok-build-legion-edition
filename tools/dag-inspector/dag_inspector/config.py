"""config.py — load a Grok DAG config into structured dataclasses.

The Grok DAG config.toml has the high-level shape::

    [subagents]
    enabled = true

    [subagents.models]
    orchestrator = "deepseek-v4-pro"
    ...

    [subagents.fallback]
    ...

    [model.deepseek-v4-pro]
    model = "deepseek-v4-pro"
    base_url = "https://api.deepseek.com/v1"
    name = "..."
    env_key = ["DEEPSEEK_API_KEY"]            # string or list
    context_window = 1000000
    api_backend = "chat_completions"           # optional
    env_http_headers = { "x-api-key" = "..." } # optional
    extra_headers = { "anthropic-version" = "..." } # optional

    [models]
    default = "deepseek-v4-pro"

    [goal]                                     # optional goal DAG
    planner_model = { model = "...", agent_type = "..." }
    ...

We surface these as ``Config`` + ``ModelBlock`` + ``DagHeader``.

Loading happens in three modes:

- ``load_active()``  — read ``~/.grok/dag-mode`` → label → preset file.
- ``load_preset(name)`` — resolve a label/alias and read the preset file.
- ``load_file(path)``  — read an arbitrary TOML config file (used by ``diff``
  and ``history``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .header import DagHeader, normalize_label, parse_header, preset_filename
from . import paths as _paths
from .toml import env_key_as_list, load as load_toml


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ModelBlock:
    """One ``[model.<id>]`` block from the config."""

    id: str
    model: str = ""
    base_url: str = ""
    name: str = ""
    env_key: List[str] = field(default_factory=list)
    context_window: int = 0
    api_backend: str = ""
    env_http_headers: Dict[str, str] = field(default_factory=dict)
    extra_headers: Dict[str, str] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    def provider(self) -> str:
        """Coarse provider bucket (deepseek/openai/anthropic/xai/openrouter/minimax/qwen/other)."""
        url = (self.base_url or "").lower()
        if "deepseek" in url:
            return "deepseek"
        if "anthropic" in url:
            return "anthropic"
        if "x.ai" in url or "xai" in url:
            return "xai"
        if "openrouter" in url:
            return "openrouter"
        if "openai" in url:
            return "openai"
        mid = (self.id or "").lower()
        if "deepseek" in mid:
            return "deepseek"
        if "claude" in mid:
            return "anthropic"
        if "grok" in mid:
            return "xai"
        if "minimax" in mid or "m3" in mid:
            return "minimax"
        if "qwen" in mid:
            return "qwen"
        return "other"


@dataclass
class GoalRole:
    """One row from ``[goal]`` (planner_model / strategist_model / skeptic_models)."""

    role: str  # planner | strategist | skeptic
    model: str = ""
    agent_type: str = "general-purpose"


@dataclass
class Config:
    """A fully-parsed DAG config."""

    path: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)
    header: DagHeader = field(default_factory=DagHeader)
    enabled: bool = False
    primaries: Dict[str, str] = field(default_factory=dict)
    fallbacks: Dict[str, str] = field(default_factory=dict)
    models: Dict[str, ModelBlock] = field(default_factory=dict)
    default_model: str = ""
    goal_roles: List[GoalRole] = field(default_factory=list)
    fork_secondary_model: str = ""
    extra_sections: Dict[str, Any] = field(default_factory=dict)

    # ---- helpers -----------------------------------------------------

    def ordered_roles(self) -> List[str]:
        """Return roles in the order they appear in ``primaries``."""
        return list(self.primaries.keys())

    def env_keys(self) -> List[str]:
        """Unique, ordered list of env keys referenced by every model block."""
        seen: List[str] = []
        for m in self.models.values():
            for k in m.env_key:
                if k not in seen:
                    seen.append(k)
        return seen

    def env_keys_missing(self) -> List[str]:
        """Subset of ``env_keys()`` not currently set in os.environ."""
        return [k for k in self.env_keys() if not os.environ.get(k)]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _parse_models_section(raw_models: Dict[str, Any]) -> Dict[str, ModelBlock]:
    out: Dict[str, ModelBlock] = {}
    for mid, block in raw_models.items():
        if not isinstance(block, dict):
            continue
        mb = ModelBlock(
            id=mid,
            model=str(block.get("model", "")),
            base_url=str(block.get("base_url", "")),
            name=str(block.get("name", "")),
            env_key=env_key_as_list(block.get("env_key")),
            context_window=int(block.get("context_window", 0) or 0),
            api_backend=str(block.get("api_backend", "")),
            env_http_headers={str(k): str(v) for k, v in (block.get("env_http_headers") or {}).items()},
            extra_headers={str(k): str(v) for k, v in (block.get("extra_headers") or {}).items()},
            raw=block,
        )
        out[mid] = mb
    return out


def _parse_goal_section(raw_goal: Dict[str, Any]) -> List[GoalRole]:
    if not isinstance(raw_goal, dict):
        return []
    out: List[GoalRole] = []
    for key in ("planner_model", "strategist_model"):
        v = raw_goal.get(key)
        if isinstance(v, dict):
            out.append(
                GoalRole(
                    role=key.replace("_model", ""),
                    model=str(v.get("model", "")),
                    agent_type=str(v.get("agent_type", "general-purpose")),
                )
            )
    skeptics = raw_goal.get("skeptic_models")
    if isinstance(skeptics, list):
        for v in skeptics:
            if isinstance(v, dict):
                out.append(
                    GoalRole(
                        role="skeptic",
                        model=str(v.get("model", "")),
                        agent_type=str(v.get("agent_type", "general-purpose")),
                    )
                )
    return out


def _extras(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Pass-through of sections that aren't part of the DAG core.

    Used by ``runtime`` to show marketplace / cli / ui / features context.
    """
    keep_keys = {"marketplace", "cli", "ui", "features"}
    return {k: v for k, v in raw.items() if k in keep_keys}


def load_file(path: str) -> Config:
    """Load an arbitrary TOML config file. Missing file → empty Config."""
    if not os.path.exists(path):
        return Config(path=path)
    raw = load_toml(path)
    with open(path, "r", encoding="utf-8") as fh:
        header_text = fh.read()
    header = parse_header(header_text)
    sub = raw.get("subagents", {}) or {}
    models = sub.get("models", {}) or {}
    fallbacks = sub.get("fallback", {}) or {}
    raw_models = raw.get("model", {}) or {}
    ui = raw.get("ui", {}) or {}
    return Config(
        path=path,
        raw=raw,
        header=header,
        enabled=bool(sub.get("enabled", False)),
        primaries={str(k): str(v) for k, v in models.items()},
        fallbacks={str(k): str(v) for k, v in fallbacks.items()},
        models=_parse_models_section(raw_models),
        default_model=str((raw.get("models") or {}).get("default", "")),
        goal_roles=_parse_goal_section(raw.get("goal") or {}),
        fork_secondary_model=str(ui.get("fork_secondary_model", "")),
        extra_sections=_extras(raw),
    )


def load_preset(name: str, home: Optional[str] = None) -> Config:
    """Resolve ``name`` (label or alias) → preset file → Config."""
    label = normalize_label(name)
    if not label:
        raise FileNotFoundError(f"unknown DAG label/alias: {name!r}")
    fname = preset_filename(label)
    if not fname:
        raise FileNotFoundError(f"no preset file mapping for label {label!r}")
    pdir = _paths.presets_dir(home or _paths.grok_home())
    path = os.path.join(pdir, fname)
    if not os.path.exists(path):
        raise FileNotFoundError(f"preset file not found: {path}")
    cfg = load_file(path)
    # Force the label to match even if header block is malformed.
    if not cfg.header.is_known:
        cfg.header.label = label.upper()
    return cfg


def load_active(home: Optional[str] = None) -> Config:
    """Load the currently-active DAG config (follows the ``dag-mode`` label)."""
    h = home or _paths.grok_home()
    mode_path = _paths.mode_file(h)
    label = ""
    if os.path.exists(mode_path):
        with open(mode_path, "r", encoding="utf-8") as fh:
            label = fh.read().strip()
    # Try to follow the dag-mode label first.
    canonical = normalize_label(label)
    if canonical:
        try:
            return load_preset(canonical, h)
        except FileNotFoundError:
            pass
    # Fall back to the active config file (whatever it currently is).
    cfg = load_file(_paths.config_file(h))
    if not cfg.header.is_known:
        # Try inferring from dag-mode anyway.
        if canonical:
            cfg.header.label = canonical.upper()
    return cfg


def load_file_or_preset(spec: str, home: Optional[str] = None) -> Config:
    """``spec`` is either a path to a file OR a label/alias.

    Distinguishes by checking if it looks like a path (has ``/`` or ends
    in ``.toml``). Falls back to ``load_preset`` otherwise.
    """
    h = home or _paths.grok_home()
    if spec.endswith(".toml") or "/" in spec or spec.startswith("."):
        # Try path first.
        path = os.path.expanduser(spec)
        if not os.path.isabs(path):
            path = os.path.join(h, path) if not spec.startswith("./") else spec
        if not os.path.exists(path):
            raise FileNotFoundError(f"config file not found: {path}")
        return load_file(path)
    return load_preset(spec, h)