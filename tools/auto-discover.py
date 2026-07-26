#!/usr/bin/env python3
"""Discover usable Legion providers and generate a working DAG preset."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import legion_common as common

PROVIDERS = [
    {
        "id": "opencode",
        "keys": ("OPENCODE_API_KEY",),
        "models": [
            ("opencode/big-pickle", "big-pickle", "OpenCode Big Pickle", 200_000),
            (
                "opencode/deepseek-v4-flash-free",
                "deepseek-v4-flash-free",
                "DeepSeek V4 Flash Free (OpenCode)",
                1_000_000,
            ),
        ],
        "endpoint": "https://api.opencode.ai/v1",
    },
    {
        "id": "nvidia",
        "keys": ("NVIDIA_API_KEY", "NVAPI_KEY"),
        "models": [
            ("nvidia/nvidia/nemotron-3-ultra-550b-a55b", "nvidia/nemotron-3-ultra-550b-a55b", "Nemotron Ultra", 128_000),
            ("nvidia/deepseek-ai/deepseek-v4-pro", "deepseek-ai/deepseek-v4-pro", "DeepSeek V4 Pro (NIM)", 1_000_000),
        ],
        "endpoint": "https://integrate.api.nvidia.com/v1",
    },
    {
        "id": "venice",
        "keys": ("VENICE_API_KEY",),
        "models": [
            ("venice/hermes-3-llama-3.1-405b", "hermes-3-llama-3.1-405b", "Hermes 3 405B (Venice)", 128_000),
            ("venice/deepseek-r1", "deepseek-r1", "DeepSeek R1 (Venice)", 128_000),
        ],
        "endpoint": "https://api.venice.ai/api/v1",
    },
    {
        "id": "deepseek",
        "keys": ("DEEPSEEK_API_KEY",),
        "models": [
            ("deepseek-v4-pro", "deepseek-v4-pro", "DeepSeek V4 Pro", 1_000_000),
            ("deepseek-v4-flash", "deepseek-v4-flash", "DeepSeek V4 Flash", 1_000_000),
        ],
        "endpoint": "https://api.deepseek.com/v1",
    },
    {
        "id": "minimax",
        "keys": ("MINIMAX_API_KEY",),
        "models": [
            ("MiniMax-M3", "MiniMax-M3", "MiniMax M3", 1_000_000),
        ],
        "endpoint": "https://api.minimax.io/v1",
    },
    {
        "id": "openrouter",
        "keys": ("OPENROUTER_API_KEY",),
        "models": [
            ("openrouter/auto", "openrouter/auto", "OpenRouter Auto", 200_000),
            ("openrouter/deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-pro", "DeepSeek V4 Pro (OpenRouter)", 128_000),
        ],
        "endpoint": "https://openrouter.ai/api/v1",
    },
    {
        "id": "anthropic",
        "keys": ("ANTHROPIC_API_KEY",),
        "models": [
            ("claude-sonnet-5", "claude-sonnet-5", "Claude Sonnet 5", 200_000),
        ],
        "endpoint": "https://api.anthropic.com/v1",
        "api_backend": "messages",
        "auth_scheme": "x_api_key",
    },
    {
        "id": "zenmux",
        "keys": ("ZENMUX_API_KEY",),
        "models": [
            ("zenmux/z-ai/glm-5.2", "z-ai/glm-5.2", "GLM 5.2 (ZenMux)", 128_000),
            ("zenmux/qwen/qwen3.7-plus", "qwen/qwen3.7-plus", "Qwen 3.7 Plus (ZenMux)", 128_000),
        ],
        "endpoint": "https://zenmux.ai/api/v1",
    },
    {
        "id": "xai",
        "keys": ("XAI_API_KEY",),
        "models": [
            ("grok-4.5", "grok-4.5", "Grok 4.5", 500_000),
        ],
        "endpoint": "https://api.x.ai/v1",
    },
    {
        "id": "kimi",
        "keys": ("KIMI_API_KEY",),
        "models": [
            ("kimi-k3", "kimi-k3", "Kimi K3", 1_000_000),
        ],
        "endpoint": "https://api.moonshot.ai/v1",
    },
    {
        "id": "openai",
        "keys": ("OPENAI_API_KEY",),
        "models": [
            ("openai/gpt-5-codex", "gpt-5-codex", "OpenAI Codex", 128_000),
        ],
        "endpoint": "https://api.openai.com/v1",
        "api_backend": "responses",
    },
    {
        "id": "gemini",
        "keys": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "models": [
            ("gemini-3.6-flash", "gemini-3.6-flash", "Gemini 3.6 Flash", 1_000_000),
        ],
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/openai",
    },
]

LOCAL_PROBES = [
    ("opencode-local", "OpenCode local server", "http://127.0.0.1:4096/v1"),
    ("cliproxy", "CLIProxyAPI", "http://127.0.0.1:8317/v1"),
    ("ollama", "Ollama", "http://127.0.0.1:11434/v1"),
    ("litellm", "LiteLLM", "http://127.0.0.1:4000/v1"),
    ("lmstudio", "LM Studio", "http://127.0.0.1:1234/v1"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect provider environment keys and reachable local OpenAI-compatible "
            "services, then generate auto-discovered.toml."
        )
    )
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="skip local HTTP endpoint probes",
    )
    parser.add_argument(
        "--activate",
        action="store_true",
        help="also merge the generated preset into the active config.toml",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="timeout in seconds for each local endpoint probe (default: 1.0)",
    )
    return parser.parse_args()


def probe_models(endpoint: str, timeout: float) -> list[str] | None:
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}/models",
        headers={"User-Agent": "LegionAutoDiscover/2.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=max(0.1, timeout)) as response:
            if response.status != 200:
                return None
            body = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return None
    data = body.get("data", [])
    if not isinstance(data, list):
        return []
    return [
        str(item["id"])
        for item in data
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]


def first_set(keys: tuple[str, ...]) -> str | None:
    return next((key for key in keys if os.environ.get(key, "").strip()), None)


def model_entry(
    *,
    model: str,
    endpoint: str,
    name: str,
    context_window: int,
    env_keys: tuple[str, ...] = (),
    api_backend: str | None = None,
    auth_scheme: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "model": model,
        "base_url": endpoint,
        "name": name,
        "context_window": context_window,
    }
    if env_keys:
        entry["env_key"] = list(env_keys)
    if api_backend:
        entry["api_backend"] = api_backend
    if auth_scheme:
        entry["auth_scheme"] = auth_scheme
    return entry


def build_preset(
    provider_ids: set[str],
    entries: dict[str, dict[str, Any]],
    local_models: list[str],
) -> tuple[str, dict[str, str]]:
    roles = {role: "grok-4.5" for role in common.CANONICAL_ROLES}

    if "gemini" in provider_ids:
        roles["explore"] = "gemini-3.6-flash"
    if "opencode" in provider_ids:
        roles.update(
            orchestrator="opencode/big-pickle",
            explore="opencode/deepseek-v4-flash-free",
            architect="opencode/big-pickle",
            implementor="opencode/big-pickle",
        )
    if "openai" in provider_ids:
        roles["implementor"] = "openai/gpt-5-codex"
    if "openrouter" in provider_ids:
        roles.update(
            orchestrator="openrouter/auto",
            architect="openrouter/auto",
            implementor="openrouter/deepseek/deepseek-v4-pro",
        )
    if "deepseek" in provider_ids:
        roles.update(
            orchestrator="deepseek-v4-pro",
            explore="deepseek-v4-flash",
            architect="deepseek-v4-pro",
            implementor="deepseek-v4-pro",
        )
    if "minimax" in provider_ids:
        roles["implementor"] = "MiniMax-M3"
    if "venice" in provider_ids:
        roles["orchestrator"] = "venice/hermes-3-llama-3.1-405b"
    if "nvidia" in provider_ids:
        roles["architect"] = "nvidia/nvidia/nemotron-3-ultra-550b-a55b"
    if "anthropic" in provider_ids:
        roles["orchestrator"] = "claude-sonnet-5"
    if "xai" in provider_ids:
        roles["verifier"] = "grok-4.5"
    elif roles["verifier"] not in entries and local_models:
        roles["verifier"] = local_models[0]
    elif roles["verifier"] not in entries:
        roles["verifier"] = roles["orchestrator"]

    if not provider_ids and local_models:
        for role in common.CANONICAL_ROLES:
            roles[role] = local_models[0]

    roles["plan"] = roles["architect"]
    roles["general-purpose"] = roles["implementor"]
    content = "# Auto-discovered by Legion. Re-run instead of hand-editing.\n\n"
    content = common.replace_table(content, "subagents", {"enabled": True})
    content = common.replace_table(content, "subagents.models", roles)
    content = common.replace_table(
        content,
        "subagents.fallback",
        {"verifier": roles["orchestrator"]},
    )
    content = common.merge_model_entries(content, entries)
    return content, roles


def main() -> int:
    args = parse_args()
    print("⚡ Discovering usable Legion providers and local model services...")
    print("=" * 68)

    provider_ids: set[str] = set()
    entries: dict[str, dict[str, Any]] = {}
    for provider in PROVIDERS:
        selected_key = first_set(provider["keys"])
        if selected_key is None:
            continue
        provider_ids.add(provider["id"])
        print(f"  [✓] Provider credential: {selected_key}")
        for catalog_id, model, name, context in provider["models"]:
            entries[catalog_id] = model_entry(
                model=model,
                endpoint=provider["endpoint"],
                name=name,
                context_window=context,
                env_keys=provider["keys"],
                api_backend=provider.get("api_backend"),
                auth_scheme=provider.get("auth_scheme"),
            )

    binaries = [
        name
        for name in ("ollama", "opencode", "litellm", "agy", "codex", "cline")
        if shutil.which(name)
    ]
    if binaries:
        print("  [i] Installed clients: " + ", ".join(binaries))

    local_catalog_ids: list[str] = []
    if not args.no_probe:
        for provider_id, label, endpoint in LOCAL_PROBES:
            models = probe_models(endpoint, args.timeout)
            if models is None:
                continue
            print(f"  [✓] Local service: {label} ({len(models)} models)")
            for model in models:
                catalog_id = f"{provider_id}/{model}"
                entries[catalog_id] = model_entry(
                    model=model,
                    endpoint=endpoint,
                    name=f"{model} ({label})",
                    context_window=200_000,
                )
                local_catalog_ids.append(catalog_id)

    content, roles = build_preset(provider_ids, entries, local_catalog_ids)
    destination = common.presets_dir() / "auto-discovered.toml"
    try:
        common.load_toml(destination) if destination.exists() else None
        common.atomic_write(destination, content, private=True)
        common.load_toml(destination)
        if args.activate:
            common.apply_preset(destination)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("\n🎯 Generated DAG mapping:")
    common.print_models(roles)
    print(f"\n✅ Saved preset to {destination}")
    if args.activate:
        print(f"✅ Activated it in {common.config_path()}")
    else:
        print("   Activate with: legion-mode auto")
    if not provider_ids and not local_catalog_ids:
        print(
            "   Note: no provider key or local service was found; the stock Grok "
            "model remains selected."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
