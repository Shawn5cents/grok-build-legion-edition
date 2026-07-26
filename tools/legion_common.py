#!/usr/bin/env python3
"""Shared, side-effect-safe configuration helpers for Legion's CLI tools."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any, Iterable, Mapping

CANONICAL_ROLES = (
    "orchestrator",
    "explore",
    "architect",
    "implementor",
    "verifier",
)
ROLE_ALIASES = {
    "plan": "architect",
    "general-purpose": "implementor",
}


def grok_home() -> Path:
    """Return the same configurable user directory used by the Rust runtime."""
    configured = os.environ.get("GROK_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".grok"


def config_path() -> Path:
    return grok_home() / "config.toml"


def presets_dir() -> Path:
    return grok_home() / "config-presets"


def bundled_presets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "presets"


def toml_quote(value: str) -> str:
    """Encode a Python string as a TOML-compatible basic string."""
    return json.dumps(value, ensure_ascii=False)


def toml_key(value: str) -> str:
    return value if re.fullmatch(r"[A-Za-z0-9_-]+", value) else toml_quote(value)


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and math.isfinite(value):
        return repr(value)
    if isinstance(value, str):
        return toml_quote(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, Mapping):
        fields = ", ".join(
            f"{toml_key(str(key))} = {toml_value(item)}"
            for key, item in value.items()
        )
        return "{ " + fields + " }"
    raise TypeError(f"unsupported TOML value: {value!r}")


def load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"cannot read valid TOML from {path}: {exc}") from exc


def load_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def atomic_write(path: Path, content: str, *, private: bool = True) -> None:
    """Atomically replace a UTF-8 file, retaining permissions when it exists."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    previous_mode = (path.stat().st_mode & 0o777) if path.exists() else None
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        mode = previous_mode if previous_mode is not None else (0o600 if private else 0o644)
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


_TABLE_HEADER_RE = re.compile(r"(?m)^[ \t]*\[([^\]\r\n]+)\][ \t]*(?:#.*)?$")


def _table_span(content: str, raw_table_name: str) -> tuple[int, int] | None:
    matches = list(_TABLE_HEADER_RE.finditer(content))
    for index, match in enumerate(matches):
        if match.group(1).strip() == raw_table_name:
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            return match.start(), end
    return None


def _format_table(raw_table_name: str, values: Mapping[str, Any]) -> str:
    lines = [f"[{raw_table_name}]"]
    for key, value in values.items():
        try:
            encoded = toml_value(value)
        except TypeError as exc:
            raise TypeError(
                f"unsupported TOML value for {raw_table_name}.{key}: {value!r}"
            ) from exc
        lines.append(f"{toml_key(str(key))} = {encoded}")
    return "\n".join(lines) + "\n"


def replace_table(content: str, raw_table_name: str, values: Mapping[str, Any]) -> str:
    """Replace one TOML table without consuming adjacent/nested tables."""
    block = _format_table(raw_table_name, values)
    span = _table_span(content, raw_table_name)
    if span is None:
        # TOML dotted tables create their parents implicitly. If a parent table
        # needs explicit scalar keys, it must be inserted before its first child.
        child_prefix = f"{raw_table_name}."
        for match in _TABLE_HEADER_RE.finditer(content):
            if match.group(1).strip().startswith(child_prefix):
                before = content[: match.start()].rstrip()
                after = content[match.start() :].lstrip("\n")
                pieces = [piece for piece in (before, block.rstrip(), after.rstrip()) if piece]
                return "\n\n".join(pieces) + "\n"
        prefix = content.rstrip()
        return f"{prefix}\n\n{block}" if prefix else block
    start, end = span
    suffix = content[end:].lstrip("\n")
    before = content[:start].rstrip()
    pieces = [piece for piece in (before, block.rstrip(), suffix.rstrip()) if piece]
    return "\n\n".join(pieces) + "\n"


def upsert_table_values(
    content: str,
    raw_table_name: str,
    values: Mapping[str, Any],
) -> str:
    """Merge scalar values into a table while retaining unrelated keys/comments."""
    span = _table_span(content, raw_table_name)
    if span is None:
        return replace_table(content, raw_table_name, values)

    start, end = span
    table_text = content[start:end].rstrip()
    lines = table_text.splitlines()
    pending = dict(values)
    key_re = re.compile(r"^([A-Za-z0-9_-]+)[ \t]*=")
    rendered_values = _format_table("_", values).splitlines()[1:]
    rendered_by_key = {
        line.split("=", 1)[0].strip(): line for line in rendered_values
    }

    updated = [lines[0]]
    for line in lines[1:]:
        match = key_re.match(line.lstrip())
        if match and match.group(1) in pending:
            key = match.group(1)
            updated.append(rendered_by_key[key])
            pending.pop(key)
        else:
            updated.append(line)
    for key in values:
        if key in pending:
            updated.append(rendered_by_key[key])

    replacement = "\n".join(updated).rstrip() + "\n"
    return content[:start] + replacement + content[end:]


def normalized_models(models: Mapping[str, str]) -> dict[str, str]:
    normalized = {str(key): str(value) for key, value in models.items()}
    for alias, canonical in ROLE_ALIASES.items():
        if canonical not in normalized and alias in normalized:
            normalized[canonical] = normalized[alias]
    for alias, canonical in ROLE_ALIASES.items():
        if canonical in normalized:
            normalized[alias] = normalized[canonical]
    return normalized


def load_subagent_models(path: Path | None = None) -> dict[str, str]:
    data = load_toml(path or config_path())
    raw = data.get("subagents", {}).get("models", {})
    if not isinstance(raw, dict):
        return {}
    return normalized_models(
        {str(key): str(value) for key, value in raw.items() if isinstance(value, str)}
    )


def write_subagent_models(
    models: Mapping[str, str],
    path: Path | None = None,
    *,
    fallback: Mapping[str, str] | None = None,
) -> None:
    target = path or config_path()
    existing = load_subagent_models(target)
    existing.update(normalized_models(models))
    ordered: dict[str, str] = {}
    for role in CANONICAL_ROLES:
        ordered[role] = existing.get(role, "grok-4.5")
    ordered["plan"] = ordered["architect"]
    ordered["general-purpose"] = ordered["implementor"]
    for key, value in existing.items():
        if key not in ordered:
            ordered[key] = value

    content = load_text(target)
    content = upsert_table_values(content, "subagents", {"enabled": True})
    content = replace_table(content, "subagents.models", ordered)
    if fallback is not None:
        content = replace_table(content, "subagents.fallback", fallback)
    _validate_generated_toml(content, target)
    atomic_write(target, content)
    ensure_model_entries(ordered.values(), target)


def _model_table_name(model_id: str) -> str:
    return f"model.{toml_quote(model_id)}"


def merge_model_entries(
    content: str,
    entries: Mapping[str, Mapping[str, Any]],
) -> str:
    for model_id, values in entries.items():
        content = upsert_table_values(content, _model_table_name(model_id), values)
    return content


def load_model_entries(path: Path | None = None) -> dict[str, dict[str, Any]]:
    data = load_toml(path or config_path())
    raw = data.get("model", {})
    if not isinstance(raw, dict):
        return {}
    return {
        str(model_id): dict(values)
        for model_id, values in raw.items()
        if isinstance(values, dict)
    }


def known_model_entries(directory: Path | None = None) -> dict[str, dict[str, Any]]:
    """Collect routable model definitions from every installed preset."""
    entries: dict[str, dict[str, Any]] = {}
    for preset in available_presets(directory):
        try:
            entries.update(load_model_entries(preset))
        except ValueError:
            # A malformed unrelated preset must not make the role editor unusable.
            continue
    return entries


def ensure_model_entries(
    model_ids: Iterable[str],
    path: Path | None = None,
    *,
    entries: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    """Copy known runtime routes for selected role models into config.toml."""
    target = path or config_path()
    known = dict(entries or known_model_entries())
    existing = load_model_entries(target)
    selected = {
        model_id: known[model_id]
        for model_id in dict.fromkeys(model_ids)
        if model_id in known and model_id not in existing
    }
    if not selected:
        return
    content = load_text(target)
    content = merge_model_entries(content, selected)
    _validate_generated_toml(content, target)
    atomic_write(target, content)


def _validate_generated_toml(content: str, path: Path) -> None:
    try:
        tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"refusing to write invalid TOML to {path}: {exc}") from exc


def apply_preset(preset_path: Path, target: Path | None = None) -> dict[str, str]:
    destination = target or config_path()
    preset = load_toml(preset_path)
    subagents = preset.get("subagents", {})
    raw_models = subagents.get("models", {}) if isinstance(subagents, dict) else {}
    if not isinstance(raw_models, dict) or not raw_models:
        raise ValueError(f"{preset_path} has no non-empty [subagents.models] table")
    models = normalized_models(
        {str(key): str(value) for key, value in raw_models.items() if isinstance(value, str)}
    )
    raw_fallback = subagents.get("fallback", {}) if isinstance(subagents, dict) else {}
    fallback = (
        {str(key): str(value) for key, value in raw_fallback.items() if isinstance(value, str)}
        if isinstance(raw_fallback, dict)
        else {}
    )

    write_subagent_models(models, destination, fallback=fallback)
    content = load_text(destination)
    raw_model_entries = preset.get("model", {})
    if isinstance(raw_model_entries, dict):
        entries = {
            str(model_id): values
            for model_id, values in raw_model_entries.items()
            if isinstance(values, dict)
        }
        try:
            content = merge_model_entries(content, entries)
        except TypeError as exc:
            raise ValueError(
                f"{preset_path} contains unsupported model values: {exc}"
            ) from exc
    _validate_generated_toml(content, destination)
    atomic_write(destination, content)
    return models


def available_presets(directory: Path | None = None) -> list[Path]:
    if directory is not None:
        if not directory.exists():
            return []
        return sorted(path for path in directory.glob("*.toml") if path.is_file())

    by_name: dict[str, Path] = {}
    for root in (bundled_presets_dir(), presets_dir()):
        if root.exists():
            by_name.update(
                {
                    path.stem: path
                    for path in root.glob("*.toml")
                    if path.is_file()
                }
            )
    return [by_name[name] for name in sorted(by_name)]


def resolve_preset(name: str) -> Path | None:
    return next((path for path in available_presets() if path.stem == name), None)


def print_models(models: Mapping[str, str]) -> None:
    labels = {
        "orchestrator": "Orchestrator",
        "explore": "Explore",
        "architect": "Architect",
        "implementor": "Implementor",
        "verifier": "Verifier",
    }
    for role in CANONICAL_ROLES:
        print(f"  {labels[role]:<12}: {models.get(role, 'grok-4.5')}")


def _switch_command(args: argparse.Namespace) -> int:
    if args.preset == "list":
        print("Available Subagent DAG Presets:")
        presets = available_presets()
        if presets:
            for preset in presets:
                print(f"  - {preset.stem}")
        else:
            print("  (none installed)")
        print(f"\nCurrent [subagents.models] in {config_path()}:")
        print_models(load_subagent_models())
        return 0

    preset_path = resolve_preset(args.preset)
    if preset_path is None:
        print(f"Error: preset {args.preset!r} is not installed or bundled", file=sys.stderr)
        return 1
    try:
        preset_data = load_toml(preset_path)
        models = apply_preset(preset_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Successfully switched DAG preset to: {args.preset}")
    print("\nUpdated [subagents.models]:")
    print_models(models)
    metadata = preset_data.get("preset", {})
    required_env = metadata.get("required_env", []) if isinstance(metadata, dict) else []
    missing = [
        name
        for name in required_env
        if isinstance(name, str) and not os.environ.get(name, "").strip()
    ]
    if missing:
        print(
            "\nWarning: these provider variables are not set in this shell: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        print(
            "The preset is active, but affected models will not authenticate "
            "until their credentials are configured.",
            file=sys.stderr,
        )
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Legion configuration helper")
    subparsers = parser.add_subparsers(dest="command", required=True)
    switch_parser = subparsers.add_parser("switch", help="apply or list DAG presets")
    switch_parser.add_argument("preset", nargs="?", default="list")
    switch_parser.set_defaults(func=_switch_command)
    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
