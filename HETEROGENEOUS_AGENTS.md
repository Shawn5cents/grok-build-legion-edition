# Heterogeneous Agent Architecture

Legion is released by Nichols AI.

This fork applies the design principles from *Agentic AI System Is a
Foreseeable Pathway to AGI* to Legion. The paper argues for routing tasks
to heterogeneous specialists, choosing an optimal rather than maximal number
of agents, composing them as a stable directed acyclic graph (DAG), and placing
contractive critic or verification edges before consequential outputs.

## Zero-Touch Provider & Model Auto-Discovery

What sets **grok-build-legion-edition** apart is its **Zero-Touch Auto-Discovery Engine** (`tools/auto-discover.py`).

Instead of manually editing TOML files, auto-discovery checks:

1. **Provider credentials**: `OPENCODE_API_KEY`, `NVIDIA_API_KEY`/`NVAPI_KEY`, `VENICE_API_KEY`, `DEEPSEEK_API_KEY`, `MINIMAX_API_KEY`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `ZENMUX_API_KEY`, `KIMI_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`/`GOOGLE_API_KEY`, and `XAI_API_KEY`.
2. **Installed AI clients**: reports `ollama`, `opencode`, `litellm`, `agy`, `codex`, and `cline` for visibility. A binary alone is not treated as a working provider.
3. **Reachable local endpoints**: probes ports 4096 (OpenCode), 8317 (CLIProxyAPI), 11434 (Ollama), 4000 (LiteLLM), and 1234 (LM Studio), then records the models actually returned by `/v1/models`.
4. **Usable runtime configuration**: generates `auto-discovered.toml` with both DAG role mappings and the `[model.*]` endpoint/auth entries required by the agent runtime.

```bash
# Auto-discover system capabilities and generate preset
./tools/auto-discover.py --activate
```

## Runtime Graph

```text
                         +-----------------------+
                         | DeepSeek V4 Pro       |
                         | router / lead         |
                         +-----------+-----------+
                                     |
                       complex task  |  trivial task -> one specialist
                          +----------+----------+
                          |                     |
                 +--------v--------+   +--------v--------+
                 | V4 Flash        |   | Nemotron 550B   |
                 | explore         |   | architect       |
                 +--------+--------+   +--------+--------+
                          +----------+----------+
                                     |
                           +---------v----------+
                           | MiniMax-M3         |
                           | implementor        |
                           | execution          |
                           +---------+----------+
                                     |
                           +---------v----------+
                           | grok-4.5           |
                           | verifier (no edit) |
                           | fallback: V4 Pro   |
                           +---------+----------+
                                     |
                               PASS --+--> final
                               FAIL --+--> one repair, one recheck
```

The router launches no more than two speculative specialists before
implementation. It does not create an agent whose output cannot affect a
downstream decision, and it forbids unbounded agent chains and critique loops.
This controls routing regret and organizational entropy while retaining
specialization.

## Consolidated Provider & Gateway Connections

To maintain 100% clean upstream Git sync without modifying Rust engine source code,
Legion connects natively to direct provider APIs, local proxy engines, and cloud gateways:

### Supported Native Provider Routes

| Local / Catalog Model ID | Provider Name | Direct / Gateway Endpoint Route | Context Window |
|---|---|---|---:|
| `opencode/big-pickle` | OpenCode Zen (Stealth) | `http://localhost:4096/v1` | 200,000 |
| `nvidia/nvidia/nemotron-3-ultra-550b-a55b` | NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | 128,000 |
| `venice/hermes-3-llama-3.1-405b` | Venice AI | `https://api.venice.ai/api/v1` | 128,000 |
| `deepseek-v4-pro` | DeepSeek AI | `https://api.deepseek.com/v1` | 1,000,000 |
| `deepseek-v4-flash` | DeepSeek AI | `https://api.deepseek.com/v1` | 1,000,000 |
| `claude-sonnet-5` | Anthropic | `https://api.anthropic.com/v1` | 200,000 |
| `gpt-5.6-sol` | OpenAI | `https://api.openai.com/v1` | 128,000 |
| `MiniMax-M3` | MiniMax | `https://api.minimax.io/v1` | 1,000,000 |
| `grok-4.5` | xAI | `https://api.x.ai/v1` | 500,000 |
| `cline-pass` | Cline Pass | `https://api.cline.bot/v1` | 200,000 |
| `openai/gpt-5-codex` | Codex | `http://localhost:8317/v1` | 128,000 |
| `kimi-k3` | Moonshot Kimi | `https://api.moonshot.cn/v1` | 1,000,000 |
| `zenmux/anthropic/claude-sonnet-5-free` | ZenMux Free Tier | `https://zenmux.ai/api/v1` | 200,000 |

## Model Configuration & Presets

Active subagent role mappings live under `[subagents.models]` in `~/.grok/config.toml`:

```toml
[subagents.models]
orchestrator    = "deepseek-v4-pro"
explore         = "deepseek-v4-flash"
architect       = "nvidia/nvidia/nemotron-3-ultra-550b-a55b"
implementor     = "MiniMax-M3"
verifier        = "grok-4.5"

# Backward-compatibility aliases for legacy engine components
plan            = "nvidia/nvidia/nemotron-3-ultra-550b-a55b"
general-purpose = "MiniMax-M3"
```

### Rate-Limit Fallback

When a subagent encounters an HTTP 429 rate limit, the orchestrator retries
once with a configured fallback model:

```toml
[subagents.fallback]
verifier = "deepseek-v4-pro"
```

### Model Preset Switcher (`tools/switch-subagents.sh`)

Switch model presets live without restarting the agent session:

```bash
# List available DAG presets
./tools/switch-subagents.sh list

# Auto-discover system providers
./tools/auto-discover.py

# Switch presets live
./tools/switch-subagents.sh auto-discovered
./tools/switch-subagents.sh big-pickle-dag
./tools/switch-subagents.sh free-legion-dag
./tools/switch-subagents.sh nvidia-nim-dag
./tools/switch-subagents.sh venice-ai-dag
./tools/switch-subagents.sh legion-dag
./tools/switch-subagents.sh cline-pass-dag
```
