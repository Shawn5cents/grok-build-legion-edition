#!/usr/bin/env python3
"""
Interactive Mode Selector & Preset Creator for Legion Grok

Allows users to switch modes effortlessly via an interactive terminal menu,
or easily create custom DAG preset profiles with zero hassle.
"""

import os
import sys
import subprocess
from pathlib import Path

HOME = Path.home()
CONFIG = HOME / ".grok" / "config.toml"
PRESETS_DIR = HOME / ".grok" / "config-presets"

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
        "title": "🌟 Standard Grok 4.5 Mode",
        "desc": "Runs standard Grok 4.5 for all subagent roles, exactly like stock grok."
    },
    {
        "key": "2",
        "preset": "legion-dag",
        "title": "🕸️ Legion Multi-Agent DAG Mode",
        "desc": "DeepSeek V4 Pro (Architect/Lead) + DeepSeek V4 Flash (Explore) + MiniMax-M3 (Implementor) + Grok 4.5 (Verifier)."
    },
    {
        "key": "3",
        "preset": "big-pickle-dag",
        "title": "🥒 OpenCode Big Pickle DAG Mode",
        "desc": "OpenCode Big Pickle (Architect/Lead) + DeepSeek Flash Free (Explore) + Nemotron 550B (Verifier)."
    },
    {
        "key": "4",
        "preset": "free-legion-dag",
        "title": "🎁 100% Free / Zero-Cost DAG Mode",
        "desc": "$0 Cost: Free Claude Sonnet 5 + Free Kimi K3 + DeepSeek Flash Free + Nemotron Ultra Free."
    },
    {
        "key": "5",
        "preset": "nvidia-nim-dag",
        "title": "🟢 NVIDIA NIM DAG Mode",
        "desc": "Nemotron 550B + DeepSeek R1 NIM + Llama 3.3 70B via integrate.api.nvidia.com."
    },
    {
        "key": "6",
        "preset": "venice-ai-dag",
        "title": "🪟 Venice AI Privacy DAG Mode",
        "desc": "Hermes 3 Llama 405B + Venice DeepSeek R1 + Qwen Coder (Zero-Data-Retention & Uncensored)."
    },
    {
        "key": "7",
        "preset": "cline-pass-dag",
        "title": "✨ Cline Pass + Codex + Kimi Code Mode",
        "desc": "Cline Pass (Architect/Lead) + Kimi K3 (Explore) + Codex Latest (Implementor) + Grok 4.5 (Verifier)."
    },
    {
        "key": "8",
        "preset": "auto-discovered",
        "title": "🔍 Zero-Touch Auto-Discovered Mode",
        "desc": "Auto-detects API keys and installed binaries on your machine and generates tailored profile."
    }
]

def switch_mode(preset):
    if not SWITCH_SCRIPT:
        print("Error: switch-subagents.sh tool not found.")
        sys.exit(1)
    subprocess.run([str(SWITCH_SCRIPT), preset], check=True)

def create_custom_preset():
    print("\n" + "=" * 65)
    print("🎨 Create Custom Subagent DAG Preset")
    print("=" * 65)
    print("Specify your preferred model ID for each role (press Enter to accept default):\n")

    try:
        preset_name = input("Preset Name [e.g., my-custom-dag]: ").strip().lower().replace(" ", "-")
        if not preset_name:
            preset_name = "custom"
        
        orchestrator = input("Orchestrator Model [default: deepseek-v4-pro]: ").strip() or "deepseek-v4-pro"
        explore      = input("Explore Model      [default: deepseek-v4-flash]: ").strip() or "deepseek-v4-flash"
        architect    = input("Architect Model    [default: deepseek-v4-pro]: ").strip() or "deepseek-v4-pro"
        implementor  = input("Implementor Model  [default: MiniMax-M3]: ").strip() or "MiniMax-M3"
        verifier     = input("Verifier Model     [default: grok-4.5]: ").strip() or "grok-4.5"
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(0)

    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    custom_file = PRESETS_DIR / f"{preset_name}.toml"

    content = f"""# Custom Preset: {preset_name}
[subagents]
enabled = true

[subagents.models]
orchestrator    = "{orchestrator}"
explore         = "{explore}"
architect       = "{architect}"
implementor     = "{implementor}"
verifier        = "{verifier}"
# Backward-compatibility aliases
plan            = "{architect}"
general-purpose = "{implementor}"

[subagents.fallback]
verifier = "{orchestrator}"
"""
    with open(custom_file, "w") as f:
        f.write(content)

    print(f"\n✅ Custom preset created at: {custom_file}")
    switch_mode(preset_name)

def show_menu():
    print("\n" + "=" * 65)
    print("⚔️  Legion Grok Mode Selector")
    print("=" * 65)
    print("Select an active operating mode for your agent sessions:\n")

    for mode in MODES:
        print(f"  [{mode['key']}] {mode['title']}")
        print(f"      ↳ {mode['desc']}\n")

    # List any user custom presets in ~/.grok/config-presets/
    custom_presets = []
    if PRESETS_DIR.exists():
        builtins = {m["preset"] for m in MODES}
        for f in sorted(PRESETS_DIR.glob("*.toml")):
            if f.stem not in builtins and f.stem != "auto-discovered":
                custom_presets.append(f.stem)

    if custom_presets:
        print("  🎨 Custom Presets:")
        for cp in custom_presets:
            print(f"      • {cp} (run 'legion-mode {cp}')")
        print("")

    print("  [c] Create a New Custom Preset")
    print("  [0] Run Zero-Touch Auto-Discovery Scan")
    print("  [q] Quit\n")

def main():
    if len(sys.argv) > 1:
        choice = sys.argv[1].lower()
        if choice in ["create", "new", "c"]:
            create_custom_preset()
            sys.exit(0)
        elif choice in ["original", "grok", "default", "1"]:
            target_preset = "grok-unified"
        elif choice in ["legion", "dag", "2"]:
            target_preset = "legion-dag"
        elif choice in ["pickle", "big-pickle", "3"]:
            target_preset = "big-pickle-dag"
        elif choice in ["free", "4"]:
            target_preset = "free-legion-dag"
        elif choice in ["nvidia", "nim", "5"]:
            target_preset = "nvidia-nim-dag"
        elif choice in ["venice", "6"]:
            target_preset = "venice-ai-dag"
        elif choice in ["cline", "codex", "7"]:
            target_preset = "cline-pass-dag"
        elif choice in ["auto", "8", "0"]:
            target_preset = "auto-discovered"
        else:
            target_preset = choice
        
        switch_mode(target_preset)
        sys.exit(0)

    show_menu()
    try:
        user_input = input("Enter selection [1-8, c, 0, or q]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(0)

    if user_input == "q" or user_input == "":
        print("No changes made.")
        sys.exit(0)
    elif user_input == "c":
        create_custom_preset()
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
            # Check if user entered a custom preset name
            custom_path = PRESETS_DIR / f"{user_input}.toml"
            if custom_path.exists():
                switch_mode(user_input)
            else:
                print("Invalid choice. No changes made.")

if __name__ == "__main__":
    main()
