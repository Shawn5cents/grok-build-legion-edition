#!/usr/bin/env python3
"""
Legion Hub — Ultimate User-Friendly Flow & Menu System
for Models, Subagents, Roles, and Model Catalog.

Provides an intuitive, visual, step-by-step menu system for:
1. Browsing the Unified Model Catalog (OpenCode Big Pickle, NVIDIA NIM, Venice AI, Free Models, SaaS, Gateways)
2. Mapping Models to Subagent DAG Roles (Orchestrator, Explore, Architect, Implementor, Verifier)
3. One-Click DAG Preset Selection (Legion, Big Pickle, Free Tier, NVIDIA NIM, Venice AI, Cline Pass, OpenRouter, ZenMux)
4. Zero-Touch System Capability Scan
5. Live Proxy & Connection Verification
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path

import legion_common as common

SCRIPT_DIR = Path(__file__).resolve().parent
SWITCH_SCRIPT = SCRIPT_DIR / "switch-subagents.sh"
AUTO_SCRIPT = SCRIPT_DIR / "auto-discover.py"

# Categorized Model Catalog
MODEL_CATALOG = {
    "OpenCode Zen & Stealth": [
        {"id": "opencode/big-pickle", "name": "Big Pickle", "ctx": "200,000", "desc": "Stealth reasoning & multi-step refactoring ($0 Free Tier)"},
        {"id": "opencode/deepseek-v4-flash-free", "name": "DeepSeek V4 Flash Free", "ctx": "1,000,000", "desc": "Ultra-fast free explorer"},
    ],
    "NVIDIA NIM": [
        {"id": "nvidia/nvidia/nemotron-3-ultra-550b-a55b", "name": "Nemotron 550B MoE", "ctx": "128,000", "desc": "High-capacity reasoning & architecture"},
        {"id": "nvidia/deepseek-ai/deepseek-v4-pro", "name": "DeepSeek V4 Pro (NIM)", "ctx": "1,000,000", "desc": "NVIDIA hardware-accelerated DeepSeek V4"},
        {"id": "nvidia/meta/llama-3.3-70b-instruct", "name": "Llama 3.3 70B (NIM)", "ctx": "128,000", "desc": "NIM general coding & implementation"},
    ],
    "Venice AI (Privacy & Uncensored)": [
        {"id": "venice/hermes-3-llama-3.1-405b", "name": "Hermes 3 Llama 405B", "ctx": "128,000", "desc": "Uncensored 405B frontier lead"},
        {"id": "venice/deepseek-r1", "name": "DeepSeek R1 (Venice)", "ctx": "128,000", "desc": "Zero-data-retention reasoning model"},
        {"id": "venice/qwen-2.5-coder-32b", "name": "Qwen 2.5 Coder (Venice)", "ctx": "128,000", "desc": "Private high-speed code generator"},
    ],
    "100% Free / Zero-Cost Tiers": [
        {"id": "zenmux/anthropic/claude-sonnet-5-free", "name": "Claude Sonnet 5 Free", "ctx": "200,000", "desc": "Zero-cost Claude Sonnet 5 via ZenMux"},
        {"id": "zenmux/moonshotai/kimi-k3-free", "name": "Kimi K3 Free", "ctx": "1,000,000", "desc": "Zero-cost 2.8T Kimi K3 model"},
        {"id": "openrouter/openrouter/free", "name": "OpenRouter Free Router", "ctx": "200,000", "desc": "Automatic $0 free tier model router"},
    ],
    "DeepSeek": [
        {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro", "ctx": "1,000,000", "desc": "1.6T parameter reasoning & architect lead"},
        {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "ctx": "1,000,000", "desc": "Ultra-fast codebase exploration specialist"},
    ],
    "Anthropic / Claude": [
        {"id": "claude-sonnet-5", "name": "Claude Sonnet 5", "ctx": "200,000", "desc": "Flagship coding & architecture model"},
        {"id": "claude-opus-5", "name": "Claude Opus 5", "ctx": "200,000", "desc": "Frontier reasoning & lead model"},
    ],
    "OpenAI / Codex": [
        {"id": "gpt-5.6-sol", "name": "GPT-5.6 Sol", "ctx": "128,000", "desc": "Flagship reasoning & complex planning"},
        {"id": "openai/gpt-5-codex", "name": "Codex Latest (gpt-5-codex)", "ctx": "128,000", "desc": "OpenAI Codex developer interface"},
    ],
    "xAI / Grok": [
        {"id": "grok-4.5", "name": "Grok 4.5", "ctx": "500,000", "desc": "Frontier verifier critic & standard engine"},
    ],
    "Moonshot / Kimi": [
        {"id": "kimi-k3", "name": "Kimi K3", "ctx": "1,000,000", "desc": "2.8T parameter Moonshot coding model"},
    ],
    "MiniMax": [
        {"id": "MiniMax-M3", "name": "MiniMax-M3", "ctx": "1,000,000", "desc": "Implementation & coding specialist"},
    ],
    "Google / Antigravity": [
        {"id": "gemini-3.6-flash", "name": "Gemini 3.6 Flash", "ctx": "1,000,000", "desc": "High-throughput fast Gemini workhorse"},
        {"id": "gemini-3.1-pro", "name": "Gemini 3.1 Pro", "ctx": "1,000,000", "desc": "Complex reasoning Gemini model"},
    ],
    "Qwen / Alibaba": [
        {"id": "qwen3.7-max", "name": "Qwen 3.7 Max", "ctx": "128,000", "desc": "Frontier agentic coding model"},
    ],
}

ROLES = [
    ("orchestrator", "🧠 Orchestrator / Lead", "Top-level coordinator and task router"),
    ("explore", "🔍 Explore Specialist", "Read-only codebase investigator"),
    ("architect", "📐 Architecture Planner", "System design and technical planner (formerly 'plan')"),
    ("implementor", "💻 Coder / Implementer", "Code modification and task execution (formerly 'general-purpose')"),
    ("verifier", "🛡️ Verifier Critic", "Read-only quality & test verifier"),
]


def available_model_catalog():
    """Return only models that have a built-in or configured runtime route."""
    routes = common.known_model_entries()
    routes.update(common.load_model_entries())
    visible = {}
    seen = set()
    for category, models in MODEL_CATALOG.items():
        usable = [
            model
            for model in models
            if model["id"] == "grok-4.5" or model["id"] in routes
        ]
        if usable:
            visible[category] = usable
            seen.update(model["id"] for model in usable)

    configured = []
    for model_id, route in routes.items():
        if model_id in seen:
            continue
        context = route.get("context_window")
        configured.append(
            {
                "id": model_id,
                "name": str(route.get("name") or model_id),
                "ctx": f"{context:,}" if isinstance(context, int) else "provider default",
                "desc": "Configured runtime model",
            }
        )
    if configured:
        visible["Other Configured Models"] = sorted(
            configured, key=lambda model: model["name"].lower()
        )
    return visible


def clear_screen():
    print("\033[H\033[2J", end="")

def load_current_config():
    try:
        return common.load_subagent_models()
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return {}

def save_models_to_config(models):
    common.write_subagent_models(models)

def browse_catalog():
    print("\n" + "=" * 70)
    print("📚 UNIFIED MODEL CATALOG (SaaS, OpenCode, NVIDIA NIM, Venice AI, Free Tiers)")
    print("=" * 70)
    
    all_flat = []
    idx = 1
    for category, models in available_model_catalog().items():
        print(f"\n📂 {category}:")
        for m in models:
            print(f"  [{idx:2d}] {m['name']:<30} (ID: `{m['id']}`) — {m['desc']} [{m['ctx']} tokens]")
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
    for category, m_list in available_model_catalog().items():
        for m in m_list:
            flat_catalog.append(m)

    for r_key, r_title, r_desc in ROLES:
        cur = models.get(r_key) or models.get("plan" if r_key == "architect" else ("general-purpose" if r_key == "implementor" else "grok-4.5"), "grok-4.5")
        print(f"\nRole: {r_title}")
        print(f"Description: {r_desc}")
        print(f"Current Model: {cur}")
        print("-" * 50)

        for i, m in enumerate(flat_catalog, 1):
            print(f"  [{i:2d}] {m['name']:<32} (`{m['id']}`)")
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
        ("legion-dag", "🕸️ Legion Multi-Agent DAG", "DeepSeek V4 Pro (Architect) + Flash (Explore) + MiniMax-M3 (Implementor) + Grok 4.5 (Verifier)"),
        ("big-pickle-dag", "🥒 Big Pickle DAG", "OpenCode Big Pickle (Architect/Lead) + DeepSeek Flash Free + Nemotron 550B"),
        ("free-legion-dag", "🎁 100% Free / Zero-Cost DAG", "$0 Cost: Free Claude Sonnet 5 + Free Kimi K3 + DeepSeek Flash Free"),
        ("nvidia-nim-dag", "🟢 NVIDIA NIM DAG", "Nemotron 550B + DeepSeek R1 NIM + Llama 3.3 70B"),
        ("venice-ai-dag", "🪟 Venice AI Privacy DAG", "Hermes 3 Llama 405B + Venice DeepSeek R1 + Qwen Coder (Zero-Data-Retention)"),
        ("cline-pass-dag", "✨ Cline Pass + Codex + Kimi", "Cline Pass + Kimi K3 + Codex Latest + Grok Verifier"),
        ("auto-discovered", "🔍 Auto-Discovered Profile", "Tailored profile based on system capability scan"),
    ]

    for idx, (p_id, p_name, p_desc) in enumerate(presets, 1):
        print(f"  [{idx}] {p_name:<32} — {p_desc}")

    print("\nSelect a preset to activate [1-8, or b to back]: ")
    try:
        ans = input().strip()
    except (KeyboardInterrupt, EOFError):
        return

    if ans.isdigit():
        val = int(ans)
        if 1 <= val <= len(presets):
            selected = presets[val - 1][0]
            if SWITCH_SCRIPT.is_file():
                if selected == "auto-discovered" and not (
                    common.presets_dir() / "auto-discovered.toml"
                ).is_file():
                    discovery = subprocess.run(
                        [sys.executable, str(AUTO_SCRIPT)],
                        check=False,
                    )
                    if discovery.returncode:
                        print("\nAuto-discovery failed; no preset was activated.")
                        return
                result = subprocess.run([str(SWITCH_SCRIPT), selected], check=False)
                if result.returncode:
                    print(f"\nCould not activate preset {selected!r}.")
                    return
                print(f"\n✅ Activated preset: {selected}")
                print("Press Enter to return to main menu...")
                input()

def view_current_dag(pause=True):
    models = load_current_config()
    print("\n" + "=" * 70)
    print("🕸️ CURRENT HETEROGENEOUS SUBAGENT DAG TOPOLOGY")
    print("=" * 70)

    orch = models.get("orchestrator", "grok-4.5")
    exp = models.get("explore", "grok-4.5")
    arch = models.get("architect") or models.get("plan", "grok-4.5")
    imp = models.get("implementor") or models.get("general-purpose", "grok-4.5")
    ver = models.get("verifier", "grok-4.5")

    print(
        f"""
  Orchestrator / Lead
  └─ {orch}
       ├─► Explore Specialist
       │   └─ {exp}
       └─► Architecture Planner
           └─ {arch}
                └─► Implementor / Coder
                    └─ {imp}
                         └─► Verifier Critic
                             └─ {ver}
                                  ├─ PASS ─► Final output
                                  └─ FAIL ─► One repair loop
"""
    )
    if pause:
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
        print(f"  • Architect    : {models.get('architect') or models.get('plan', 'grok-4.5')}")
        print(f"  • Implementor  : {models.get('implementor') or models.get('general-purpose', 'grok-4.5')}")
        print(f"  • Verifier     : {models.get('verifier', 'grok-4.5')}")
        print("-" * 70)
        print("  [1] 📚 Browse Model Catalog (Context Windows & Descriptions)")
        print("  [2] 🎯 Step-by-Step Subagent Role Assignment Flow")
        print("  [3] 🎛️ Select DAG Preset Profile (Legion, Big Pickle, Free Tier, NIM, Venice AI)")
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
            if not AUTO_SCRIPT.is_file():
                print(f"Auto-discovery tool is missing at {AUTO_SCRIPT}.")
                continue
            result = subprocess.run(
                [sys.executable, str(AUTO_SCRIPT), "--activate"],
                check=False,
            )
            if result.returncode:
                print("Auto-discovery failed; the active configuration was not changed.")
            print("Press Enter to return to main menu...")
            input()
        elif choice == "6":
            print("\n🚀 Launching Legion Agent Session...")
            try:
                os.execvp("legion", ["legion"])
            except FileNotFoundError:
                print("Could not find 'legion' on PATH. Re-run install.sh.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Open Legion's interactive model, role, and preset control hub."
    )
    parser.add_argument(
        "--show-dag",
        action="store_true",
        help="print the active DAG and exit",
    )
    return parser.parse_args()

if __name__ == "__main__":
    arguments = parse_args()
    try:
        if arguments.show_dag:
            view_current_dag(pause=False)
        else:
            main_menu()
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
