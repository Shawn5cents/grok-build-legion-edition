# Heterogeneous agent architecture

Legion is released by Nichols AI.

This fork applies the design principles from *Agentic AI System Is a
Foreseeable Pathway to AGI* to Legion. The paper argues for routing tasks
to heterogeneous specialists, choosing an optimal rather than maximal number
of agents, composing them as a stable directed acyclic graph (DAG), and placing
contractive critic or verification edges before consequential outputs.

## Zero-Touch Provider & Model Auto-Discovery

What sets **grok-build-legion-edition** apart is its **Zero-Touch Auto-Discovery Engine** (`tools/auto-discover.py`).

Instead of manually editing TOML files or wiring providers in Rust, running auto-discovery automatically scans:
1. **Environment API Keys**: Detects `DEEPSEEK_API_KEY`, `MINIMAX_API_KEY`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `ZENMUX_API_KEY`, `KIMI_API_KEY`, `CLINE_API_KEY`, `XAI_API_KEY`.
2. **Installed CLI Tools**: Detects `Ollama`, `OpenCode`, `LiteLLM`, `Legion`, `Horde`, and `CLIProxyAPI`.
3. **Active Local Endpoints**: Probes HTTP ports 8317 (CLIProxyAPI), 11434 (Ollama), 4000 (LiteLLM), 1234 (LM Studio).
4. **Auto-Configures Best DAG Profile**: Instantly generates `auto-discovered.toml` tailored to your machine's exact installed keys and tools!

```bash
# Auto-discover system capabilities and generate preset
./tools/auto-discover.py

# Activate auto-discovered DAG preset
./tools/switch-subagents.sh auto-discovered
```

## Runtime graph

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
                 | V4 Flash        |   | V4 Pro          |
                 | explore         |   | plan            |
                 +--------+--------+   +--------+--------+
                          +----------+----------+
                                     |
                           +---------v----------+
                           | MiniMax-M3         |
                           | general-purpose    |
                           | implementation     |
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

## Consolidated Provider Gateway (`CLIProxyAPI`)

To maintain 100% clean upstream Git sync without modifying Rust engine source code,
all providers (OpenCode, OpenRouter, ZenMux, Kilo Code, Cline Pass, Codex, Kimi Code, DeepSeek, MiniMax, Anthropic, xAI) route through a high-performance local **`CLIProxyAPI` Go Server** listening on `http://localhost:8317/v1`.

### Supported Provider Routes

| Local ID | Provider model ID | Gateway Route | Context Window |
|---|---|---|---:|
| `deepseek-v4-pro` | `deepseek-v4-pro` | `http://localhost:8317/v1` | 1,000,000 |
| `deepseek-v4-flash` | `deepseek-v4-flash` | `http://localhost:8317/v1` | 1,000,000 |
| `MiniMax-M3` | `MiniMax-M3` | `http://localhost:8317/v1` | 1,000,000 |
| `grok-4.5` | `grok-4.5` | `http://localhost:8317/v1` | 500,000 |
| `cline-pass` | `cline-default` | `https://api.cline.bot/v1` | 200,000 |
| `codex-latest` | `gpt-5-codex` | `http://localhost:8317/v1` | 128,000 |
| `kimi-code-k3` | `kimi-k3` | `http://localhost:8317/v1` | 1,000,000 |

## Model Configuration & Presets

Active subagent role mappings live under `[subagents.models]` in `~/.grok/config.toml`:

```toml
[subagents.models]
orchestrator    = "deepseek-v4-pro"
explore         = "deepseek-v4-flash"
plan            = "deepseek-v4-pro"
general-purpose = "MiniMax-M3"
verifier        = "grok-4.5"
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
./tools/switch-subagents.sh legion-dag
./tools/switch-subagents.sh cline-pass-dag
```
