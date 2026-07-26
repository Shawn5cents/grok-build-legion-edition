#!/usr/bin/env python3
"""Interactive preset selector and custom DAG preset creator for Legion."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import legion_common as common

SCRIPT_DIR = Path(__file__).resolve().parent
SWITCH_SCRIPT = SCRIPT_DIR / "switch-subagents.sh"
AUTO_SCRIPT = SCRIPT_DIR / "auto-discover.py"

MODES = [
    {
        "key": "1",
        "preset": "grok-unified",
        "aliases": {"original", "grok", "default"},
        "title": "🌟 Standard Grok Mode",
        "desc": "Uses the normal Grok model for every subagent role.",
    },
    {
        "key": "2",
        "preset": "legion-dag",
        "aliases": {"legion", "dag"},
        "title": "🕸️ Legion Multi-Agent DAG",
        "desc": "DeepSeek lead/explore, NVIDIA architect, MiniMax implementor, Grok verifier.",
    },
    {
        "key": "3",
        "preset": "big-pickle-dag",
        "aliases": {"pickle", "big-pickle"},
        "title": "🥒 OpenCode Big Pickle DAG",
        "desc": "OpenCode lead/explore with specialized implementation and verification.",
    },
    {
        "key": "4",
        "preset": "free-legion-dag",
        "aliases": {"free"},
        "title": "🎁 Free-Tier DAG",
        "desc": "Uses provider free-tier routes; provider credentials may still be required.",
    },
    {
        "key": "5",
        "preset": "nvidia-nim-dag",
        "aliases": {"nvidia", "nim"},
        "title": "🟢 NVIDIA NIM DAG",
        "desc": "Routes specialist roles through NVIDIA NIM.",
    },
    {
        "key": "6",
        "preset": "venice-ai-dag",
        "aliases": {"venice"},
        "title": "🪟 Venice AI Privacy DAG",
        "desc": "Routes the DAG through Venice AI models.",
    },
    {
        "key": "7",
        "preset": "cline-pass-dag",
        "aliases": {"cline", "codex"},
        "title": "✨ Cline Pass + Codex DAG",
        "desc": "Uses Cline Pass, Kimi, Codex, and Grok specialist roles.",
    },
    {
        "key": "8",
        "preset": "auto-discovered",
        "aliases": {"auto"},
        "title": "🔍 Auto-Discovered DAG",
        "desc": "Builds a profile from credentials and reachable local model services.",
    },
]


def switch_mode(preset: str) -> None:
    if not SWITCH_SCRIPT.is_file():
        raise RuntimeError(f"preset switcher not found at {SWITCH_SCRIPT}")
    result = subprocess.run([str(SWITCH_SCRIPT), preset], check=False)
    if result.returncode:
        raise RuntimeError(f"could not activate preset {preset!r}")


def run_auto_discovery() -> None:
    if not AUTO_SCRIPT.is_file():
        raise RuntimeError(f"auto-discovery tool not found at {AUTO_SCRIPT}")
    result = subprocess.run([sys.executable, str(AUTO_SCRIPT)], check=False)
    if result.returncode:
        raise RuntimeError("auto-discovery failed")


def sanitize_preset_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9._-]+", "-", value.strip().lower()).strip(".-")
    return cleaned or "custom"


def create_custom_preset() -> None:
    print("\n" + "=" * 65)
    print("🎨 Create Custom Subagent DAG Preset")
    print("=" * 65)
    print("Press Enter to accept each default.\n")
    try:
        preset_name = sanitize_preset_name(input("Preset name [custom]: "))
        models = {
            "orchestrator": input("Orchestrator model [grok-4.5]: ").strip() or "grok-4.5",
            "explore": input("Explore model [grok-4.5]: ").strip() or "grok-4.5",
            "architect": input("Architect model [grok-4.5]: ").strip() or "grok-4.5",
            "implementor": input("Implementor model [grok-4.5]: ").strip() or "grok-4.5",
            "verifier": input("Verifier model [grok-4.5]: ").strip() or "grok-4.5",
        }
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return

    models["plan"] = models["architect"]
    models["general-purpose"] = models["implementor"]
    content = common.replace_table("", "subagents", {"enabled": True})
    content = common.replace_table(content, "subagents.models", models)
    content = common.replace_table(
        content,
        "subagents.fallback",
        {"verifier": models["orchestrator"]},
    )
    destination = common.presets_dir() / f"{preset_name}.toml"
    common.atomic_write(destination, f"# Custom preset: {preset_name}\n\n{content}", private=False)
    print(f"\n✅ Created {destination}")
    switch_mode(preset_name)


def show_menu() -> None:
    print("\n" + "=" * 65)
    print("⚔️  Legion Mode Selector")
    print("=" * 65)
    print("Select an operating mode:\n")
    for mode in MODES:
        print(f"  [{mode['key']}] {mode['title']}")
        print(f"      {mode['desc']}\n")

    builtins = {mode["preset"] for mode in MODES}
    custom = [path.stem for path in common.available_presets() if path.stem not in builtins]
    if custom:
        print("  Custom presets: " + ", ".join(custom))
    print("  [c] Create a custom preset")
    print("  [0] Re-run auto-discovery and activate it")
    print("  [q] Quit\n")


def resolve_mode(value: str) -> str | None:
    lowered = value.lower()
    for mode in MODES:
        if lowered in {mode["key"], mode["preset"], *mode["aliases"]}:
            return mode["preset"]
    if common.resolve_preset(lowered) is not None:
        return lowered
    dag_variant = f"{lowered}-dag"
    return dag_variant if common.resolve_preset(dag_variant) is not None else None


def activate(value: str) -> None:
    preset = resolve_mode(value)
    if preset is None:
        raise RuntimeError(
            f"unknown mode {value!r}; run 'legion-mode --list' to see available presets"
        )
    if preset == "auto-discovered" and not (
        common.presets_dir() / "auto-discovered.toml"
    ).is_file():
        run_auto_discovery()
    switch_mode(preset)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select or create a Legion heterogeneous-agent DAG preset."
    )
    parser.add_argument("mode", nargs="?", help="preset name, alias, or menu number")
    parser.add_argument("--list", action="store_true", help="list installed presets")
    parser.add_argument(
        "--discover",
        action="store_true",
        help="run capability discovery and activate the generated preset",
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="interactively create and activate a custom preset",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.list:
            return subprocess.run([str(SWITCH_SCRIPT), "list"], check=False).returncode
        if args.discover:
            run_auto_discovery()
            switch_mode("auto-discovered")
            return 0
        if args.create or args.mode in {"create", "new", "c"}:
            create_custom_preset()
            return 0
        if args.mode:
            activate(args.mode)
            return 0

        show_menu()
        try:
            choice = input("Enter selection [1-8, c, 0, or q]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            return 0
        if choice in {"", "q"}:
            print("No changes made.")
            return 0
        if choice == "c":
            create_custom_preset()
        elif choice == "0":
            run_auto_discovery()
            switch_mode("auto-discovered")
        else:
            activate(choice)
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
