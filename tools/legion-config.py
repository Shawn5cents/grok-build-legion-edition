#!/usr/bin/env python3
"""
Ultra User-Friendly Model & Config Editor for Legion Grok

Provides a fast, interactive terminal menu to change models for individual subagent roles,
set all roles to a single LLM at once, and manage configuration settings with zero TOML editing required.
"""

import os
import sys
import re
import json
import urllib.request
from pathlib import Path

HOME = Path.home()
CONFIG = HOME / ".grok" / "config.toml"
PRESETS_DIR = HOME / ".grok" / "config-presets"

AVAILABLE_MODELS = [
    {"id": "grok-4.5", "name": "Grok 4.5 (xAI)", "desc": "Frontier reasoning & verification"},
    {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro", "desc": "1M context frontier reasoning & lead"},
    {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "desc": "1M context ultra-fast exploration"},
    {"id": "deepseek-reasoner", "name": "DeepSeek R1 Reasoner", "desc": "Chain-of-thought architecture planner"},
    {"id": "MiniMax-M3", "name": "MiniMax-M3", "desc": "1M context implementation & coding specialist"},
    {"id": "cline-pass", "name": "Cline Pass Default", "desc": "Cline Pass subscription gateway model"},
    {"id": "codex-latest", "name": "Codex Latest (gpt-5-codex)", "desc": "OpenAI Codex / Copilot interface"},
    {"id": "kimi-code-k3", "name": "Kimi K3 (Moonshot)", "desc": "Moonshot AI 2.8T parameter coding model"},
    {"id": "gemini-3.5-flash", "name": "Gemini 3.5 Flash", "desc": "Google Antigravity fast model"},
    {"id": "openrouter/auto", "name": "OpenRouter Auto", "desc": "Universal SaaS OpenRouter gateway"},
]

ROLES = [
    ("orchestrator", "🧠 Orchestrator / Lead", "Top-level coordinator and task router"),
    ("explore", "🔍 Explore Specialist", "Read-only codebase investigator"),
    ("plan", "📐 Architecture Planner", "System design and implementation planner"),
    ("general-purpose", "💻 Coder / Implementer", "Code modification and task execution"),
    ("verifier", "🛡️ Verifier Critic", "Read-only quality & test verifier"),
]

def load_current_config():
    if not CONFIG.exists():
        return {}
    with open(CONFIG) as f:
        content = f.read()
    
    models = {}
    pattern = r'\[subagents\.models\]\n((?:.+\n)*?)(?=\n\[|$)'
    match = re.search(pattern, content)
    if match:
        for line in match.group(1).splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                models[k.strip()] = v.strip().strip('"').strip("'")
    return models

def save_models_to_config(models):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG.exists():
        with open(CONFIG) as f:
            content = f.read()
    else:
        content = "[subagents.models]\n"

    new_block_lines = ["[subagents.models]"]
    for role_key, _, _ in ROLES:
        val = models.get(role_key, "grok-4.5")
        new_block_lines.append(f'{role_key:<15} = "{val}"')
    new_block = "\n".join(new_block_lines) + "\n"

    pattern = r'(\[subagents\.models\]\n)((?:.*\n)*?)(?=\n\[|$)'
    match = re.search(pattern, content)
    if match:
        new_config = content[:match.start()] + new_block + content[match.end():]
    else:
        new_config = content + "\n" + new_block

    with open(CONFIG, "w") as f:
        f.write(new_config)

def set_all_roles_to_model(model_id):
    models = {}
    for r_key, _, _ in ROLES:
        models[r_key] = model_id
    save_models_to_config(models)
    print(f"\n✅ All subagent roles updated to: '{model_id}'!")

def interactive_set_all_roles(models):
    print("\nSelect a model to apply to ALL subagent roles:")
    for idx, m in enumerate(AVAILABLE_MODELS, 1):
        print(f"  [{idx}] {m['name']} (`{m['id']}`)")
    print("  [c] Enter Custom Model ID")
    print("  [b] Back\n")

    try:
        choice = input("Select model for ALL roles [1-10, c, or b]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return

    if choice == "b" or choice == "":
        return
    elif choice == "c":
        custom_id = input("Enter custom model ID: ").strip()
        if custom_id:
            set_all_roles_to_model(custom_id)
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(AVAILABLE_MODELS):
                selected = AVAILABLE_MODELS[idx]
                set_all_roles_to_model(selected["id"])
        except ValueError:
            print("Invalid selection.")

def interactive_change_role_model(models, role_key, role_title):
    print(f"\nSelect a new model for {role_title}:")
    print(f"Current: {models.get(role_key, 'grok-4.5')}\n")

    for idx, m in enumerate(AVAILABLE_MODELS, 1):
        print(f"  [{idx}] {m['name']} (`{m['id']}`) — {m['desc']}")
    print("  [c] Enter Custom Model ID")
    print("  [b] Back\n")

    try:
        choice = input("Select model [1-10, c, or b]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return

    if choice == "b" or choice == "":
        return
    elif choice == "c":
        custom_id = input("Enter custom model ID: ").strip()
        if custom_id:
            models[role_key] = custom_id
            print(f"Set {role_title} to '{custom_id}'")
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(AVAILABLE_MODELS):
                selected = AVAILABLE_MODELS[idx]
                models[role_key] = selected["id"]
                print(f"Set {role_title} to '{selected['id']}'")
        except ValueError:
            print("Invalid selection.")

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--all", "-a"] and len(sys.argv) > 2:
            set_all_roles_to_model(sys.argv[2])
            sys.exit(0)

    while True:
        models = load_current_config()
        print("\n" + "=" * 65)
        print("🛠️  Legion Easy Model & Config Editor")
        print("=" * 65)
        print("Current Active Role Models:\n")

        for idx, (r_key, r_title, r_desc) in enumerate(ROLES, 1):
            cur_m = models.get(r_key, "grok-4.5")
            print(f"  [{idx}] {r_title:<26} : {cur_m}")

        print("\n  [a] Set ALL Roles to a Single LLM")
        print("  [s] Save & Apply Config")
        print("  [r] Reset to Default Presets Menu")
        print("  [q] Quit\n")

        try:
            choice = input("Select option [1-5, a, s, r, or q]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            sys.exit(0)

        if choice == "q":
            print("Exited.")
            sys.exit(0)
        elif choice == "a":
            interactive_set_all_roles(models)
        elif choice == "s":
            save_models_to_config(models)
            print("\n✅ Configuration saved to ~/.grok/config.toml!")
            sys.exit(0)
        elif choice == "r":
            legion_mode_bin = HOME / ".local" / "bin" / "legion-mode"
            if legion_mode_bin.exists():
                os.execv(str(legion_mode_bin), [str(legion_mode_bin)])
            else:
                sys.exit(0)
        else:
            try:
                role_idx = int(choice) - 1
                if 0 <= role_idx < len(ROLES):
                    r_key, r_title, _ = ROLES[role_idx]
                    interactive_change_role_model(models, r_key, r_title)
                    save_models_to_config(models)
            except ValueError:
                print("Invalid input.")

if __name__ == "__main__":
    main()
