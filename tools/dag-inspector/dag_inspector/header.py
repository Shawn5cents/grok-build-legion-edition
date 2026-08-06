"""header.py — parse the DAG label header block at the top of a preset.

The DAG presets start with a comment block like::

    # =============================================================================
    # DAG label: MIXED  (aliases: diverse, multi-family, ensemble, cross)
    # Use for: daily work with true cross-family verification ...
    # Cost: LOW–MEDIUM  |  Restart TUI required after:  dag mixed
    # =============================================================================
    # Multi-family economy DAG — strongest verification at economy pricing.
    #
    # PRIMARY:
    #   main chat / orchestrator  deepseek-v4-pro     (proven, reliable)
    # ...

We extract:
- ``label``    — the canonical label (``FULL`` | ``ECONOMY`` | ``MIXED``)
- ``aliases``  — list of accepted command names (``max``, ``flagship``, etc.)
- ``use_for``  — short "Use for:" line (if present)
- ``cost``     — "Cost: HIGH" portion (if present)
- ``switch``   — "dag full" command name (if present)
- ``description`` — everything between the closing `# ====` and the first
  TOML section (``[...]``)

A label that doesn't match the expected block is treated as ``unknown`` but
the function still returns useful defaults so callers can show partial info.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


LABEL_RE = re.compile(r"#\s*DAG\s+label\s*:\s*([A-Za-z0-9_-]+)", re.IGNORECASE)
ALIASES_RE = re.compile(r"aliases?\s*:\s*([^)\n]+)", re.IGNORECASE)
USE_FOR_RE = re.compile(r"Use\s+for\s*:\s*([^\n#]+)", re.IGNORECASE)
COST_RE = re.compile(r"Cost\s*:\s*([^\n#|]+)", re.IGNORECASE)
SWITCH_RE = re.compile(r"after\s*:\s*[`'\"]?\s*(dag\s+[a-zA-Z_-]+)", re.IGNORECASE)


@dataclass
class DagHeader:
    """Parsed DAG label header block."""

    label: str = "unknown"
    aliases: List[str] = field(default_factory=list)
    use_for: str = ""
    cost: str = ""
    switch: str = ""
    description: str = ""

    @property
    def is_known(self) -> bool:
        return self.label.upper() in {"FULL", "ECONOMY", "MIXED"}

    def all_names(self) -> List[str]:
        """Return label + aliases (lowercased) — used to normalize inputs."""
        names = [self.label.lower()] if self.label else []
        names.extend(a.lower() for a in self.aliases)
        return names


def parse_header(text: str) -> DagHeader:
    """Parse the DAG header block from a TOML config string."""
    header = DagHeader()

    # The header is everything before the FIRST non-comment line that starts
    # with a TOML section header OR the first uncommented key.
    # Easier: split on the closing "=====" line.
    raw_lines = text.splitlines()

    # Walk until we leave the comment block.
    comment_lines: List[str] = []
    in_header = True
    seen_first_eq = False
    closing_eq_seen = False

    for line in raw_lines:
        stripped = line.strip()
        if in_header:
            if stripped.startswith("#"):
                comment_lines.append(stripped)
                if re.match(r"^#\s*=+", stripped):
                    if seen_first_eq and not closing_eq_seen:
                        # Second `=====` line ends the block.
                        closing_eq_seen = True
                    else:
                        seen_first_eq = True
                continue
            if not stripped:
                comment_lines.append(line)
                continue
            # First non-comment, non-blank line: leave header.
            in_header = False

    header_text = "\n".join(comment_lines)
    # Drop leading/trailing `=====` fence lines so they don't show up in the
    # description.
    header_text = re.sub(r"^#\s*=+\s*\n", "", header_text, flags=re.MULTILINE)
    header_text = re.sub(r"\n#\s*=+\s*$", "", header_text, flags=re.MULTILINE)

    m = LABEL_RE.search(header_text)
    if m:
        header.label = m.group(1).strip().upper()
    m = ALIASES_RE.search(header_text)
    if m:
        aliases = m.group(1)
        # Strip surrounding parens if present (because we matched "aliases:" inside "(...)").
        aliases = aliases.replace("(", " ").replace(")", " ")
        # Strip "aliases" prefix if it's still there.
        aliases = re.sub(r"^aliases\s*:\s*", "", aliases, flags=re.IGNORECASE)
        header.aliases = [a.strip() for a in aliases.split(",") if a.strip()]
    m = USE_FOR_RE.search(header_text)
    if m:
        header.use_for = m.group(1).strip()
    m = COST_RE.search(header_text)
    if m:
        header.cost = m.group(1).strip()
    m = SWITCH_RE.search(header_text)
    if m:
        header.switch = m.group(1).strip()

    # Description = the FIRST comment block immediately after the CLOSING
    # `# ====` fence — typically a one-or-two-line tagline. We wait until
    # we've seen TWO `=====` lines (opening + closing) so the header
    # metadata block is not captured as the description.
    desc_lines: List[str] = []
    fence_count = 0
    after_close = False
    section_markers = (
        "PRIMARY:",
        "FALLBACK:",
        "AUTH:",
        "ENV:",
        "NOTES:",
    )
    for line in raw_lines:
        stripped = line.strip()
        if not after_close:
            if re.match(r"^#\s*=+", stripped):
                fence_count += 1
                if fence_count >= 2:
                    after_close = True
            continue
        # after_close: we're past the closing `=====`
        if not stripped:
            # Blank line ends the description (next block is a new section).
            if desc_lines:
                break
            continue
        if not stripped.startswith("#"):
            break
        body = stripped.lstrip("# ").rstrip()
        # A "section header" comment like "# PRIMARY:" ends the description.
        if any(body.upper().startswith(m) for m in section_markers):
            break
        # Skip purely-decorative `# ====` lines.
        if re.match(r"^=+", body):
            continue
        desc_lines.append(body)

    # Strip leading/trailing blank lines.
    while desc_lines and not desc_lines[0].strip():
        desc_lines.pop(0)
    while desc_lines and not desc_lines[-1].strip():
        desc_lines.pop()
    header.description = "\n".join(desc_lines)

    return header


def parse_header_from_file(path: str) -> DagHeader:
    with open(path, "r", encoding="utf-8") as fh:
        return parse_header(fh.read())


# ---------------------------------------------------------------------------
# Alias normalization (used by config.load_preset and CLI argument parsing)
# ---------------------------------------------------------------------------


# Canonical map. Lowercase keys → canonical label.
ALIAS_MAP = {
    # FULL
    "full": "full", "max": "full", "flagship": "full", "best": "full",
    "best-value": "full", "bestvalue": "full",
    # ECONOMY
    "economy": "economy", "econ": "economy", "cheap": "economy",
    "daily": "economy", "cost": "economy", "deepseek": "economy", "budget": "economy",
    # MIXED
    "mixed": "mixed", "diverse": "mixed", "multi-family": "mixed",
    "multifamily": "mixed", "ensemble": "mixed", "cross": "mixed",
    "cross-family": "mixed", "crossfamily": "mixed",
}


def normalize_label(name: Optional[str]) -> Optional[str]:
    """Map any alias to the canonical label. None / unknown → None."""
    if not name:
        return None
    key = name.strip().lower()
    return ALIAS_MAP.get(key)


PRESET_FILES = {
    "full": "full-dag.toml",
    "economy": "economy-dag.toml",
    "mixed": "mixed-dag.toml",
}


def preset_filename(label: str) -> Optional[str]:
    return PRESET_FILES.get(label.lower())