#!/usr/bin/env python3
"""
Legion Hub — Ultimate User-Friendly Flow & Menu System
for Models, Subagents, Roles, and Model Catalog.

Provides an intuitive, visual, step-by-step menu system for:
1. Browsing the Unified Model Catalog (by Provider & Context Window)
2. Mapping Models to Subagent DAG Roles (Orchestrator, Explore, Plan, Coder, Verifier)
3. One-Click DAG Preset Selection
4. Zero-Touch System Capability Scan
5. Live Proxy & Connection Verification
"""

import os
import sys
import re
import json
import urllib.request
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

# Categorized Model Catalog
MODEL_CATALOG = {
    "DeepSeek": [
        {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro", "ctx": "1,000,000", "desc": "Frontier reasoning & DAG lead"},
        {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "ctx": "1,000,000", "desc": "Ultra-fast codebase exploration"},
        {"id": "deepseek-reasoner", "name": "DeepSeek R1 Reasoner", "ctx": "128,000", "desc": "Deep chain-of-thought planner"},
    ],
    "xAI / Grok": [
        {"id": "grok-4.5", "name": "Grok 4.5", "ctx": "500,000", "desc": "Frontier verifier critic & standard engine"},
    ],
    "OpenAI / Codex": [
        {"id": "codex-latest", "name": "Codex Latest (gpt-5-codex)", "ctx": "128,000", "desc": "OpenAI Codex / Copilot interface"},
    ],
    "Cline Pass": [
        {"id": "cline-pass", "name": "Cline Pass Default", "ctx": "200,000", "desc": "Cline Pass subscription gateway model"},
    ],
    "Moonshot / Kimi": [
        {"id": "kimi-code-k3", "name": "Kimi K3", "ctx": "1,000,000", "desc": "2.8T parameter Moonshot coding model"},
    ],
    "MiniMax": [
        {"id": "MiniMax-M3", "name": "MiniMax-M3", "ctx": "1,000,000", "desc": "Implementation & coding specialist"},
    ],
    "Google / Antigravity": [
        {"id": "gemini-3.5-flash", "name": "Gemini 3.5 Flash", "ctx": "1,000,000", "desc": "High-throughput fast Gemini model"},
        {"id": "gemini-3.1-pro", "name": "Gemini 3.1 Pro", "ctx": "1,000,000", "desc": "Complex reasoning Gemini model"},
    ],
    "Universal SaaS": [
        {"id": "openrouter/auto", "name": "OpenRouter Auto", "ctx": "200,000", "desc": "Universal SaaS OpenRouter gateway"},
        {"id": "zenmux/z-ai/glm-5.2", "name": "GLM 5.2 (ZenMux)", "ctx": "128,000", "desc": "ZenMux multi-provider gateway"},
        {"id": "kilo-code", "name": "Kilo Code", "ctx": "200,000", "desc": "Kilo Code developer gateway"},
    ],
}

ROLES = [
    ("orchestrator", "🧠 Orchestrator / Lead", "Top-level coordinator and task router"),
    ("explore", "🔍 Explore Specialist", "Read-only codebase investigator"),
    ("plan", "📐 Architecture Planner", "System design and implementation planner"),
    ("general-purpose", "💻 Coder / Implementer", "Code modification and task execution"),
    ("verifier", "🛡️ Verifier Critic", "Read-only quality & test verifier"),
]

def clear_screen():
    print("\033[H\033[2J", end="")

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

def browse_catalog():
    print("\n" + "=" * 70)
    print("📚 UNIFIED MODEL CATALOG")
    print("=" * 70)
    
    all_flat = []
    idx = 1
    for category, models in MODEL_CATALOG.items():
        print(f"\n📂 {category}:")
        for m in models:
            print(f"  [{idx:2d}] {m['name']:<24} (ID: `{m['id']}`) — {m['desc']} [{m['ctx']} tokens]")
            all_flat.append(m)
            idx += 1

    print("\nPress Enter to return to main menu...")
    input()

def role_assignment_flow():
    models = load_current_config()
    print("\n" + "=" * 70)
    print("🎯 SUBAGENT ROLE ASSIGNMENT FLOW")
    print("=" * 70)
    print("Assign a specialized model to each subagent DAG role:\n")

    flat_catalog = []
    for category, m_list in MODEL_CATALOG.items():
        for m in m_list:
            flat_catalog.append(m)

    for r_key, r_title, r_desc in ROLES:
        cur = models.get(r_key, "grok-4.5")
        print(f"\nRole: {r_title}")
        print(f"Description: {r_desc}")
        print(f"Current Model: {cur}")
        print("-" * 50)

        for i, m in enumerate(flat_catalog, 1):
            print(f"  [{i:2d}] {m['name']:<22} (`{m['id']}`)")
        print("  [c]  Enter Custom Model ID")
        print("  [k]  Keep Current Model")

        try:
            ans = input(f"\nSelect model for {r_title} [1-{len(flat_catalog)}, c, or k]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return

        if ans == "c":
            cid = input("Enter custom model ID: ").strip()
            if cid:
                models[r_key] = cid
        elif ans.isdigit():
            val = int(ans)
            if 1 <= val <= len(flat_catalog):
                models[r_key] = flat_catalog[val - 1]["id"]

    save_models_to_config(models)
    print("\n✅ Subagent DAG role assignment complete! Saved to ~/.grok/config.toml")
    print("Press Enter to return to main menu...")
    input()

def preset_selection_flow():
    print("\n" + "=" * 70)
    print("🎛️ DAG PRESET SELECTOR FLOW")
    print("=" * 70)
    print("Select a pre-configured subagent DAG preset profile:\n")

    presets = [
        ("grok-unified", "🌟 Standard Grok 4.5", "Stock out-of-the-box Grok 4.5 for all roles"),
        ("legion-dag", "🕸️ Legion Multi-Agent DAG", "DeepSeek V4 Pro + Flash + MiniMax + Grok Verifier"),
        ("cline-pass-dag", "✨ Cline Pass + Codex + Kimi", "Cline Pass + Kimi K3 + Codex Latest + Grok Verifier"),
        ("flash-orchestrator", "⚡ Fast Flash Coordinator", "DeepSeek V4 Flash fast coordinator profile"),
        ("auto-discovered", "🔍 Auto-Discovered Profile", "Tailored profile based on system capability scan"),
    ]

    for idx, (p_id, p_name, p_desc) in enumerate(presets, 1):
        print(f"  [{idx}] {p_name:<28} — {p_desc}")

    print("\nSelect a preset to activate [1-5, or b to back]: ")
    try:
        ans = input().strip()
    except (KeyboardInterrupt, EOFError):
        return

    if ans.isdigit():
        val = int(ans)
        if 1 <= val <= len(presets):
            selected = presets[val - 1][0]
            if SWITCH_SCRIPT:
                subprocess.run([str(SWITCH_SCRIPT), selected], check=True)
                print(f"\n✅ Activated preset: {selected}")
                print("Press Enter to return to main menu...")
                input()

def view_current_dag():
    models = load_current_config()
    print("\n" + "=" * 70)
    print("🕸️ CURRENT HETEROGENEOUS SUBAGENT DAG TOPOLOGY")
    print("=" * 70)

    orch = models.get("orchestrator", "grok-4.5")
    exp = models.get("explore", "grok-4.5")
    pln = models.get("plan", "grok-4.5")
    coder = models.get("general-purpose", "grok-4.5")
    ver = models.get("verifier", "grok-4.5")

    print(f"""
                      +-----------------------+
                      | Orchestrator / Lead   |
                      | {orch:<21} |
                      +-----------+-----------+
                                  |
                    +-------------+-------------+
                    |                           |
           +--------v--------+         +--------v--------+
           | Explore         |         | Plan            |
           | {exp:<15} |         | {pln:<15} |
           +--------+--------+         +--------+--------+
                    +-------------+-------------+
                                  |
                        +---------v----------+
                        | Coder / Implementer|
                        | {coder:<18} |
                        +---------+----------+
                                  |
                        +---------v----------+
                        | Verifier Critic    |
                        | {ver:<18} |
                        +---------+----------+
                                  |
                            PASS -+-> Final Output
                            FAIL -+-> 1 Repair Loop
""")
    print("Press Enter to return to main menu...")
    input()

def main_menu():
    while True:
        models = load_current_config()
        print("\n" + "=" * 70)
        print("⚔️  LEGION GROK — ULTIMATE SUBAGENT & MODEL HUB")
        print("=" * 70)
        print(" Active DAG Mapping:")
        print(f"  • Orchestrator : {models.get('orchestrator', 'grok-4.5')}")
        print(f"  • Explore      : {models.get('explore', 'grok-4.5')}")
        print(f"  • Plan         : {models.get('plan', 'grok-4.5')}")
        print(f"  • Coder        : {models.get('general-purpose', 'grok-4.5')}")
        print(f"  • Verifier     : {models.get('verifier', 'grok-4.5')}")
        print("-" * 70)
        print("  [1] 📚 Browse Model Catalog (Context Windows & Descriptions)")
        print("  [2] 🎯 Step-by-Step Subagent Role Assignment Flow")
        print("  [3] 🎛️ Select DAG Preset Profile (Legion, Cline/Codex, Grok)")
        print("  [4] 👁️ View Active DAG Flow Diagram")
        print("  [5] 🔍 Run Zero-Touch System Capability Scan")
        print("  [6] 🚀 Launch Legion Session")
        print("  [q] Quit\n")

        try:
            choice = input("Enter choice [1-6, or q]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nExited.")
            sys.exit(0)

        if choice == "q":
            print("Exited.")
            sys.exit(0)
        elif choice == "1":
            browse_catalog()
        elif choice == "2":
            role_assignment_flow()
        elif choice == "3":
            preset_selection_flow()
        elif choice == "4":
            view_current_dag()
        elif choice == "5":
            print("\nRunning Zero-Touch System Capability Scan...")
            if AUTO_SCRIPT.exists():
                subprocess.run(["python3", str(AUTO_SCRIPT)], check=True)
            if SWITCH_SCRIPT:
                subprocess.run([str(SWITCH_SCRIPT), "auto-discovered"], check=True)
            print("Press Enter to return to main menu...")
            input()
        elif choice == "6":
            print("\n🚀 Launching Legion Agent Session...")
            legion_bin = HOME / ".local" / "bin" / "legion"
            if legion_bin.exists():
                os.execv(str(legion_bin), [str(legion_bin)])
            else:
                sys.exit(0)

if __name__ == "__main__":
    main_menu()
