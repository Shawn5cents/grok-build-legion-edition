#!/usr/bin/env python3
"""Interactive editor for Legion's subagent role-to-model mapping."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import legion_common as common

AVAILABLE_MODELS = [
    ("grok-4.5", "Grok 4.5", "Stock Grok model"),
    ("deepseek-v4-pro", "DeepSeek V4 Pro", "Reasoning and orchestration"),
    ("deepseek-v4-flash", "DeepSeek V4 Flash", "Fast codebase exploration"),
    ("MiniMax-M3", "MiniMax M3", "Implementation and coding"),
    ("openai/gpt-5-codex", "OpenAI Codex", "Coding and implementation"),
    ("kimi-k3", "Kimi K3", "Long-context coding"),
    ("gemini-3.6-flash", "Gemini 3.6 Flash", "Fast long-context exploration"),
    ("openrouter/auto", "OpenRouter Auto", "Provider-side model routing"),
    ("opencode/big-pickle", "OpenCode Big Pickle", "OpenCode coding model"),
]

ROLES = [
    ("orchestrator", "🧠 Orchestrator / Lead"),
    ("explore", "🔍 Explore Specialist"),
    ("architect", "📐 Architecture Planner"),
    ("implementor", "💻 Coder / Implementer"),
    ("verifier", "🛡️ Verifier Critic"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Edit Legion's model assignment for each heterogeneous-agent role."
    )
    parser.add_argument(
        "--all",
        "-a",
        metavar="MODEL_ID",
        help="set every canonical role (and compatibility aliases) to MODEL_ID",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="print the active role mapping without opening the menu",
    )
    return parser.parse_args()


def save(models: dict[str, str]) -> None:
    common.write_subagent_models(models)


def set_all(model_id: str) -> None:
    cleaned = model_id.strip()
    if not cleaned:
        raise ValueError("model ID cannot be empty")
    save({role: cleaned for role in common.CANONICAL_ROLES})
    print(f"✅ All subagent roles now use {cleaned!r}.")


def available_models() -> list[tuple[str, str, str]]:
    routes = common.known_model_entries()
    routes.update(common.load_model_entries())
    visible = [
        model
        for model in AVAILABLE_MODELS
        if model[0] == "grok-4.5" or model[0] in routes
    ]
    seen = {model[0] for model in visible}
    for model_id, route in sorted(routes.items()):
        if model_id not in seen:
            visible.append(
                (
                    model_id,
                    str(route.get("name") or model_id),
                    "Configured runtime model",
                )
            )
    return visible


def choose_model(prompt: str) -> str | None:
    models = available_models()
    print(f"\n{prompt}")
    for index, (model_id, name, description) in enumerate(models, 1):
        print(f"  [{index}] {name} ({model_id}) — {description}")
    print("  [c] Enter a custom model ID")
    print("  [b] Back")
    try:
        choice = input(
            f"Select model [1-{len(models)}, c, or b]: "
        ).strip().lower()
    except (KeyboardInterrupt, EOFError):
        return None
    if choice in {"", "b"}:
        return None
    if choice == "c":
        try:
            custom = input("Custom model ID: ").strip()
        except (KeyboardInterrupt, EOFError):
            return None
        return custom or None
    if choice.isdigit() and 1 <= int(choice) <= len(models):
        return models[int(choice) - 1][0]
    print("Invalid selection.")
    return None


def show(models: dict[str, str]) -> None:
    for role, title in ROLES:
        print(f"  {title:<28} : {models.get(role, 'grok-4.5')}")


def run_menu() -> int:
    while True:
        try:
            models = common.load_subagent_models()
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print("\n" + "=" * 65)
        print("🛠️  Legion Model & Role Editor")
        print("=" * 65)
        print("Current active role models:\n")
        for index, (role, title) in enumerate(ROLES, 1):
            print(f"  [{index}] {title:<28} : {models.get(role, 'grok-4.5')}")
        print("\n  [a] Set all roles to one model")
        print("  [r] Open the preset selector")
        print("  [q] Quit\n")
        try:
            choice = input("Select [1-5, a, r, or q]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            return 0

        if choice in {"", "q"}:
            print("Exited.")
            return 0
        if choice == "a":
            selected = choose_model("Select a model for every role:")
            if selected:
                set_all(selected)
            continue
        if choice == "r":
            mode_tool = Path(__file__).resolve().parent / "legion-mode.py"
            return subprocess.run([sys.executable, str(mode_tool)], check=False).returncode
        if choice.isdigit() and 1 <= int(choice) <= len(ROLES):
            role, title = ROLES[int(choice) - 1]
            selected = choose_model(
                f"Select a model for {title} (current: {models.get(role, 'grok-4.5')}):"
            )
            if selected:
                models[role] = selected
                save(models)
                print(f"✅ {title} now uses {selected!r}.")
            continue
        print("Invalid selection.")


def main() -> int:
    args = parse_args()
    try:
        if args.all is not None:
            set_all(args.all)
            return 0
        if args.show:
            show(common.load_subagent_models())
            return 0
        return run_menu()
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
