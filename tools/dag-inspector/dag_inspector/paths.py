"""paths.py — filesystem locations for dag-inspector.

All locations resolve through ``GROK_HOME`` so the tool works regardless of
the user's actual home directory. Override on the command line via
``--grok-home`` or the ``GROK_HOME`` environment variable.
"""

from __future__ import annotations

import os
from glob import glob
from typing import List


def grok_home() -> str:
    """Return the Grok home directory (override via env / flag)."""
    return os.environ.get("GROK_HOME", os.path.expanduser("~/.grok"))


def config_file(home: str = None) -> str:
    """The active config that the Grok TUI reads at session start."""
    return os.path.join(home or grok_home(), "config.toml")


def mode_file(home: str = None) -> str:
    """Plain-text file with the current DAG label (``full`` | ``economy`` | ``mixed``)."""
    return os.path.join(home or grok_home(), "dag-mode")


def log_file(home: str = None) -> str:
    """Unified JSONL session log — subagent spawn/complete events live here."""
    return os.path.join(home or grok_home(), "logs", "unified.jsonl")


def presets_dir(home: str = None) -> str:
    """Directory of named preset configs (``full-dag.toml`` etc.)."""
    return os.path.join(home or grok_home(), "config-presets")


def credentials_file(home: str = None) -> str:
    """TOML of API keys — used by ``validate`` to flag unset env_keys."""
    return os.path.join(home or grok_home(), "credentials.toml")


def backup_glob(home: str = None) -> List[str]:
    """Sorted list of config backup files (newest first).

    Matches ``config.toml.bak-*`` patterns produced by ``dag-switch.sh`` and
    earlier swap operations. Files with a non-numeric / non-date prefix
    (e.g. ``-configD``) are kept — ``cmd_history`` filters / parses them.
    """
    pattern = os.path.join(home or grok_home(), "config.toml.bak-*")
    files = glob(pattern)
    # Sort by filename descending (timestamp strings sort lexicographically).
    files.sort(reverse=True)
    return files


# Public re-exports — convenient for callers that only want the helpers.
GROK_HOME = grok_home()
LOG_FILE = log_file(GROK_HOME)
MODE_FILE = mode_file(GROK_HOME)
PRESETS_DIR = presets_dir(GROK_HOME)
CONFIG_FILE = config_file(GROK_HOME)
CREDENTIALS_FILE = credentials_file(GROK_HOME)
BACKUP_GLOB = backup_glob(GROK_HOME)