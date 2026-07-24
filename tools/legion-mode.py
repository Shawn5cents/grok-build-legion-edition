#!/usr/bin/env python3
"""
Interactive Mode Selector for Legion Grok

Allows users to switch modes effortlessly via an interactive terminal menu or simple numeric selection.
"""

import os
import sys
import subprocess
from pathlib import Path

HOME = Path.home()
CONFIG = HOME / ".grok" / "config.toml"
PRESETS_DIR = HOME / ".grok" / "config-presets"

# Resolve switch-subagents.sh location
possible_switch_locations = [
    Path(__file__).resolve().parent / "switch-subagents.sh",
    HOME / "Desktop" / "grok-build-legion-edition" / "grok-build-legion-edition-main" / "tools" / "switch-subagents.sh",
    Path.cwd() / "tools" / "switch-subagents.sh",
]

SWITCH_SCRIPT = next((p for p in possible_switch_locations if p.exists()), None)
AUTO_SCRIPT = Path(__file__).resolve().parent / "auto-discover.py"
if not AUTO_SCRIPT.exists():
    AUTO_SCRIPT = HOME / "Desktop" / "grok-build-legion-edition" / "grok-build-legion-edition-main" / "tools" / "auto-discover.py"

MODES = [
    {
        "key": "1",
        "preset": "grok-unified",
        "title": "🌟 Standard Grok 4.5 (Original Out-of-the-Box Mode)",
        "desc": "Runs standard Grok 4.5 for all subagent roles, exactly like stock grok."
    },
    {
        "key": "2",
        "preset": "legion-dag",
        "title": "🕸️ Legion Multi-Agent DAG Mode",
        "desc": "DeepSeek V4 Pro (Lead/Plan) + Flash (Explore) + MiniMax-M3 (Coder) + Grok 4.5 (Verifier)."
    },
    {
        "key": "3",
        "preset": "cline-pass-dag",
        "title": "✨ Cline Pass + Codex + Kimi Code Mode",
        "desc": "Cline Pass (Lead/Plan) + Kimi K3 (Explore) + Codex Latest (Coder) + Grok 4.5 (Verifier)."
    },
    {
        "key": "4",
        "preset": "flash-orchestrator",
        "title": "⚡ Fast Flash Coordinator Mode",
        "desc": "DeepSeek V4 Flash (Fast Lead & Explore) + MiniMax-M3 (Coder) + Grok 4.5 (Verifier)."
    },
    {
        "key": "5",
        "preset": "auto-discovered",
        "title": "🔍 Zero-Touch Auto-Discovered Mode",
        "desc": "Auto-detects API keys and installed binaries on your machine and generates tailored profile."
    }
]

def show_menu():
    print("\n" + "=" * 65)
    print("⚔️  Legion Grok Mode Selector")
    print("=" * 65)
    print("Select an active operating mode for your agent sessions:\n")

    for mode in MODES:
        print(f"  [{mode['key']}] {mode['title']}")
        print(f"      ↳ {mode['desc']}\n")

    print("  [0] Run Zero-Touch Auto-Discovery Scan")
    print("  [q] Quit\n")

def switch_mode(preset):
    if not SWITCH_SCRIPT:
        print("Error: switch-subagents.sh tool not found.")
        sys.exit(1)
    subprocess.run([str(SWITCH_SCRIPT), preset], check=True)

def main():
    if len(sys.argv) > 1:
        choice = sys.argv[1].lower()
        if choice in ["original", "grok", "default", "1"]:
            target_preset = "grok-unified"
        elif choice in ["legion", "dag", "2"]:
            target_preset = "legion-dag"
        elif choice in ["cline", "codex", "3"]:
            target_preset = "cline-pass-dag"
        elif choice in ["flash", "4"]:
            target_preset = "flash-orchestrator"
        elif choice in ["auto", "5"]:
            target_preset = "auto-discovered"
        else:
            target_preset = choice
        
        switch_mode(target_preset)
        sys.exit(0)

    show_menu()
    try:
        user_input = input("Enter selection [1-5, 0, or q]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(0)

    if user_input == "q" or user_input == "":
        print("No changes made.")
        sys.exit(0)
    elif user_input == "0":
        print("\nRunning Zero-Touch Auto-Discovery...")
        if AUTO_SCRIPT.exists():
            subprocess.run(["python3", str(AUTO_SCRIPT)], check=True)
        switch_mode("auto-discovered")
    else:
        selected_mode = next((m for m in MODES if m["key"] == user_input), None)
        if selected_mode:
            print(f"\nActivating {selected_mode['title']}...")
            switch_mode(selected_mode["preset"])
        else:
            print("Invalid choice. No changes made.")

if __name__ == "__main__":
    main()
