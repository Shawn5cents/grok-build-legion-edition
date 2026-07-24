#!/usr/bin/env python3
"""
Zero-Touch Provider & Model Auto-Discovery for Legion Grok

Auto-detects:
1. Environment API keys (DEEPSEEK, OPENROUTER, MINIMAX, ANTHROPIC, ZENMUX, XAI, KIMI, CLINE, OPENAI, CODEX, KILO, AGY/ANTIGRAVITY)
2. Installed CLI AI binaries & tools (Ollama, OpenCode, LiteLLM, CLIProxyAPI, Horde, Legion, agy, codex, cline)
3. Running local HTTP proxy & model endpoints (CLIProxyAPI:8317, Ollama:11434, LiteLLM:4000, LMStudio:1234)
4. Configured credentials in ~/.claude, ~/.gemini, ~/.cli-proxy-api, ~/.opencode, ~/.cline

Automatically populates ~/.grok/config.toml with discovered models and generates optimal DAG role mappings!
"""

import os
import sys
import json
import shutil
import urllib.request
import urllib.error
import re
from pathlib import Path

HOME = Path.home()
CONFIG_FILE = HOME / ".grok" / "config.toml"
PRESETS_DIR = HOME / ".grok" / "config-presets"

# Key environment variable definitions including Cline, Codex, Kilo Code, and AGY (Antigravity)
KEY_MAP = {
    "CLINE_API_KEY": {
        "provider": "cline",
        "models": [
            {"id": "cline-pass", "name": "Cline Pass Default", "url": "https://api.cline.bot/v1", "ctx": 200000},
        ]
    },
    "CLINE_PASS_KEY": {
        "provider": "cline",
        "models": [
            {"id": "cline-pass", "name": "Cline Pass Default", "url": "https://api.cline.bot/v1", "ctx": 200000},
        ]
    },
    "DEEPSEEK_API_KEY": {
        "provider": "deepseek",
        "models": [
            {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro", "url": "https://api.deepseek.com/v1", "ctx": 1000000},
            {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash", "url": "https://api.deepseek.com/v1", "ctx": 1000000},
        ]
    },
    "CODEX_API_KEY": {
        "provider": "codex",
        "models": [
            {"id": "codex-latest", "name": "Codex Latest (gpt-5-codex)", "url": "http://localhost:8317/v1", "ctx": 128000},
        ]
    },
    "KILO_API_KEY": {
        "provider": "kilocode",
        "models": [
            {"id": "kilo-code", "name": "Kilo Code Default", "url": "http://localhost:8317/v1", "ctx": 200000},
        ]
    },
    "AGY_API_KEY": {
        "provider": "antigravity",
        "models": [
            {"id": "gemini-3.5-flash", "name": "Gemini 3.5 Flash (AGY)", "url": "https://generativelanguage.googleapis.com", "ctx": 1000000},
            {"id": "gemini-3.1-pro", "name": "Gemini 3.1 Pro (AGY)", "url": "https://generativelanguage.googleapis.com", "ctx": 1000000},
        ]
    },
    "ANTIGRAVITY_API_KEY": {
        "provider": "antigravity",
        "models": [
            {"id": "gemini-3.5-flash", "name": "Gemini 3.5 Flash (AGY)", "url": "https://generativelanguage.googleapis.com", "ctx": 1000000},
        ]
    },
    "MINIMAX_API_KEY": {
        "provider": "minimax",
        "models": [
            {"id": "MiniMax-M3", "name": "MiniMax-M3", "url": "https://api.minimax.io/v1", "ctx": 1000000},
        ]
    },
    "OPENROUTER_API_KEY": {
        "provider": "openrouter",
        "models": [
            {"id": "openrouter/auto", "name": "OpenRouter Auto Routing", "url": "https://openrouter.ai/api/v1", "ctx": 200000},
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet (OpenRouter)", "url": "https://openrouter.ai/api/v1", "ctx": 200000},
            {"id": "deepseek/deepseek-r1", "name": "DeepSeek R1 (OpenRouter)", "url": "https://openrouter.ai/api/v1", "ctx": 128000},
        ]
    },
    "ANTHROPIC_API_KEY": {
        "provider": "anthropic",
        "models": [
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "url": "https://api.anthropic.com/v1", "ctx": 200000, "backend": "messages"},
        ]
    },
    "ZENMUX_API_KEY": {
        "provider": "zenmux",
        "models": [
            {"id": "zenmux/z-ai/glm-5.2", "name": "GLM 5.2 (ZenMux)", "url": "https://zenmux.ai/api/v1", "ctx": 128000},
            {"id": "zenmux/qwen/qwen3.7-plus", "name": "Qwen 3.7 Plus (ZenMux)", "url": "https://zenmux.ai/api/v1", "ctx": 128000},
        ]
    },
    "XAI_API_KEY": {
        "provider": "xai",
        "models": [
            {"id": "grok-4.5", "name": "Grok 4.5", "url": "https://api.x.ai/v1", "ctx": 500000},
        ]
    },
    "KIMI_API_KEY": {
        "provider": "kimi",
        "models": [
            {"id": "kimi-k3", "name": "Kimi K3 (Moonshot)", "url": "https://api.moonshot.cn/v1", "ctx": 1000000},
        ]
    }
}

HTTP_PROBES = [
    {"name": "CLIProxyAPI", "port": 8317, "url": "http://localhost:8317/v1"},
    {"name": "Ollama Local", "port": 11434, "url": "http://localhost:11434/v1"},
    {"name": "LiteLLM Proxy", "port": 4000, "url": "http://localhost:4000/v1"},
    {"name": "LM Studio Local", "port": 1234, "url": "http://localhost:1234/v1"},
]

def check_http_endpoint(endpoint):
    url = f"{endpoint['url']}/models"
    req = urllib.request.Request(url, headers={"User-Agent": "GrokAutoDiscover/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                models = [m.get("id") for m in data.get("data", []) if "id" in m]
                return True, models
    except Exception:
        pass
    return False, []

def main():
    print("⚡ Auto-Discovering Installed Tools, Credentials, and Services...")
    print("=" * 65)

    discovered_keys = {}
    for env_var, spec in KEY_MAP.items():
        val = os.environ.get(env_var)
        if val and len(val.strip()) > 0:
            discovered_keys[env_var] = spec
            print(f"  [✓] Environment API Key: {env_var}")

    discovered_binaries = []
    for bin_name in ["ollama", "opencode", "litellm", "legion", "horde", "agy", "codex", "cline", "go", "python3"]:
        path = shutil.which(bin_name)
        if path:
            discovered_binaries.append((bin_name, path))
            print(f"  [✓] Binary Installed: {bin_name} -> {path}")

    # Config dir checks
    for cfg_dir_name in [".cline", ".claude", ".gemini", ".opencode", ".cli-proxy-api"]:
        dir_path = HOME / cfg_dir_name
        if dir_path.exists():
            print(f"  [✓] Configuration Directory: ~/{cfg_dir_name}")

    desktop_cliproxy = HOME / "Desktop" / "CLIProxyAPI-main"
    if desktop_cliproxy.exists():
        print(f"  [✓] Desktop Tool Found: CLIProxyAPI at {desktop_cliproxy}")

    discovered_services = []
    for probe in HTTP_PROBES:
        alive, models = check_http_endpoint(probe)
        if alive:
            discovered_services.append((probe, models))
            print(f"  [✓] Active HTTP Service: {probe['name']} (Port {probe['port']}) — {len(models)} models available")

    # Optimal DAG Role Selection based on discovered capabilities
    planner_model = "grok-4.5"
    coder_model = "grok-4.5"
    explore_model = "grok-4.5"
    orchestrator_model = "grok-4.5"
    verifier_model = "grok-4.5"

    if "CLINE_API_KEY" in discovered_keys or "CLINE_PASS_KEY" in discovered_keys or shutil.which("cline") or (HOME / ".cline").exists():
        orchestrator_model = "cline-pass"
        planner_model = "cline-pass"

    if "CODEX_API_KEY" in discovered_keys or shutil.which("codex"):
        coder_model = "codex-latest"

    if "AGY_API_KEY" in discovered_keys or "ANTIGRAVITY_API_KEY" in discovered_keys or shutil.which("agy"):
        if orchestrator_model == "grok-4.5":
            orchestrator_model = "gemini-3.5-flash"
        explore_model = "gemini-3.5-flash"

    if "DEEPSEEK_API_KEY" in discovered_keys:
        orchestrator_model = "deepseek-v4-pro"
        planner_model = "deepseek-v4-pro"
        explore_model = "deepseek-v4-flash"
        coder_model = "deepseek-v4-pro"
    elif "OPENROUTER_API_KEY" in discovered_keys:
        orchestrator_model = "anthropic/claude-3.5-sonnet"
        planner_model = "anthropic/claude-3.5-sonnet"
        coder_model = "deepseek/deepseek-r1"

    if "MINIMAX_API_KEY" in discovered_keys:
        coder_model = "MiniMax-M3"

    print("\n🎯 Auto-Configuring Optimal Heterogeneous DAG Mapping:")
    print(f"  • Orchestrator : {orchestrator_model}")
    print(f"  • Explore      : {explore_model}")
    print(f"  • Plan         : {planner_model}")
    print(f"  • Coder        : {coder_model}")
    print(f"  • Verifier     : {verifier_model}")

    # Generate or update config.toml
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)

    toml_content = f"""# Auto-Discovered Config generated by tools/auto-discover.py

[subagents.models]
orchestrator    = "{orchestrator_model}"
explore         = "{explore_model}"
plan            = "{planner_model}"
general-purpose = "{coder_model}"
verifier        = "{verifier_model}"

[subagents.fallback]
verifier = "{orchestrator_model}"
"""

    # Write discovered auto-generated preset
    auto_preset = PRESETS_DIR / "auto-discovered.toml"
    with open(auto_preset, "w") as f:
        f.write(toml_content)

    print(f"\n✅ Auto-Discovery complete! Saved preset to: {auto_preset}")
    print("   Run './tools/switch-subagents.sh auto-discovered' to activate your detected setup anytime!")

if __name__ == "__main__":
    main()
