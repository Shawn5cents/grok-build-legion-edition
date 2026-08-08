# `/dag` Slash Commands — DAG Preset Switcher

The `/dag` slash commands let you switch between Legion Multi-Agent DAG presets
directly from within the TUI, without leaving your session. They're backed by a
skill (`dag/SKILL.md`) and a shell script (`tools/dag-switch.sh`).

> **Current release:** v0.2.120. The role tables below reflect the presets as
> retested on 2026-08-06. For the agent-level release map — commit lineage,
> closed and open fix tickets, the code map, and the build/install gotcha — see
> [`docs/v0.2.120.md`](./v0.2.120.md).

## Commands

| Command | Action |
|---|---|
| `/dag`, `/dag status` | Show which DAG preset is active, current models, and cost tier |
| `/dag full` | Switch to the **flagship multi-vendor** preset (Grok 4.5 main, Claude Opus 5 plan/impl, GPT-5.6 Sol architect, DeepSeek verify) |
| `/dag mixed` | Switch to the **multi-family economy** preset (DeepSeek main/impl, MiniMax M3 plan/architect, Qwen3 Flash verify) |
| `/dag economy` | Switch to the **DeepSeek-primary daily driver** (DeepSeek for all roles, cost-optimized) |
| `/dag list` | List all available presets with aliases |

## Architecture

```
/dag full
    │
    ▼
dag/SKILL.md          ← Skill: interprets the slash command, calls dag-switch.sh
    │
    ▼
dag-switch.sh         ← Shell: copies preset to config.toml, writes dag-mode label
    │
    ├── config-presets/full-dag.toml       ← Full preset (grok-4.5 + Claude + GPT + DeepSeek)
    ├── config-presets/mixed-dag.toml      ← Mixed preset (DeepSeek + MiniMax + Qwen)
    ├── config-presets/economy-dag.toml    ← Economy preset (DeepSeek-primary)
    │
    ▼
~/.grok/config.toml   ← Active config (overwritten by switch)
~/.grok/dag-mode       ← Active label ("full", "mixed", or "economy")
```

## How It Works

1. **Skill dispatch**: When you type `/dag full` in the TUI, the `dag` skill
   matches, and the LLM calls `dag-switch.sh full`.

2. **Backup**: Before overwriting `config.toml`, the script creates a timestamped
   backup at `~/.grok/config.toml.bak-dag-{mode}-{timestamp}`.

3. **Preset application**: The chosen preset (`full-dag.toml`, `mixed-dag.toml`, or
   `economy-dag.toml`) is copied to `config.toml`.

4. **Label**: The active mode is written to `~/.grok/dag-mode` so `dag status` and
   the health monitor can report it.

5. **Restart required**: Config binds at TUI session start. After any switch, you
   must quit the TUI and restart from a fresh terminal.

## Presets

### FULL (`/dag full`) — Flagship Multi-Vendor

| Role | Model |
|---|---|
| Orchestrator | `grok-4.5` |
| Explore | `deepseek-v4-flash` |
| Plan / Implementor | `claude-opus-5` |
| Architect | `gpt-5.6-sol` |
| Verifier | `grok-4.5` (fallback: `deepseek-v4-pro`) |
| General-purpose | `deepseek-v4-pro` |

**Cost**: HIGH. Use for complex multi-file work, hard bugs, or when economy is stuck.

**Note (v0.2.120):** FULL verifier primary is `grok-4.5` (schema-safe). See `docs/v0.2.120.md`.

**Requires**: `XAI_API_KEY`, `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`.

### MIXED (`/dag mixed`) — Multi-Family Economy

| Role | Model |
|---|---|
| Orchestrator | `deepseek-v4-pro` |
| Explore | `deepseek-v4-flash` |
| Plan | `minimax-m3` |
| Architect | `gpt-5.6-luna` |
| Implementor | `minimax-m3` |
| Verifier | `qwen3-flash` (fallback: `deepseek-v4-flash`) |
| General-purpose | `deepseek-v4-pro` |

**Cost**: LOW–MEDIUM. Best daily driver — true cross-family verification catches bugs
a single-model DAG misses. Different LLM families for different roles.

**Requires**: `DEEPSEEK_API_KEY`, `MINIMAX_API_KEY`, and `OPENROUTER_API_KEY`
(Qwen is the verifier **primary** as of v0.2.120, not just a fallback). OpenAI
optional for Luna fallbacks.

**Note:** DeepSeek, MiniMax, and Qwen models ship with
`supports_structured_output = false`, so those agent types use the
StructuredOutput tool path instead of a native `response_format` request (these
providers return HTTP 400 for that schema type). If the verifier primary still
hard-fails on a schema request, the subagent falls back once to
`deepseek-v4-flash` — that is expected behavior, not an error.

### ECONOMY (`/dag economy`) — DeepSeek-Primary Daily Driver

| Role | Model |
|---|---|
| All roles | `deepseek-v4-pro` (primary) |
| Explore | `deepseek-v4-flash` (cheap breadth) |

**Cost**: LOW–MEDIUM. Simplest setup — still a real multi-role DAG, not a single-model
blob. Cross-vendor fallbacks only fire if those keys exist.

**Requires**: `DEEPSEEK_API_KEY` at minimum. OpenAI/XAI optional for fallbacks.

## DAG Health Monitor

`tools/dag-health.sh` runs every 60 seconds via LaunchAgent to verify the TUI
process has all required API keys in its environment. Missing keys mean provider
subagents silently fall back to SessionToken auth and 401 — the DAG looks healthy
but never calls the provider.

It also scans `~/.grok/logs/unified.jsonl` for recent inference/auth failures.

**Alerts**: A single persistent macOS critical alert appears when problems are
detected. Once dismissed, that specific problem class is silenced permanently
(until you run `: > ~/.grok/logs/dag-health.last` to reset).

## DAG Watch (real-time subagent failure alerts)

`tools/dag-watch-daemon.sh` tails `~/.grok/logs/unified.jsonl` and fires a macOS
Notification Center banner + Basso sound on every `subagent failed` event.

```bash
dag-watch on       # start (LaunchAgent)
dag-watch off      # stop
dag-watch status   # running?
dag-watch log      # tail the log
```

Notifications sanitize multiline API errors (newlines/quotes previously broke
`osascript` and were swallowed silently). Notify attempts are also appended to
`~/.grok/logs/dag-watch-notify.log` for proof of delivery.

## Files

| File | Purpose |
|---|---|
| `skills/dag/SKILL.md` | Skill definition that registers the `/dag` slash commands |
| `tools/dag-switch.sh` | Shell script that swaps `config.toml` between presets |
| `tools/dag-health.sh` | Health monitor for DAG provider key status |
| `tools/dag-watch.sh` | Toggle wrapper for the failure monitor |
| `tools/dag-watch-daemon.sh` | Real-time subagent failure → macOS notification |
| `tools/dag-preset-smoke.py` | API smoke-test every primary model in each labeled preset |
| `tools/dag-presets/full-dag.toml` | Full flagship preset |
| `tools/dag-presets/mixed-dag.toml` | Mixed multi-family preset |
| `tools/dag-presets/economy-dag.toml` | Economy DeepSeek-primary preset |

## Installation

Preferred: run `./install.sh` from the repo root. It builds the binary, installs
labeled DAG presets into `~/.grok/config-presets/`, installs `dag` / `dag-watch`
helpers, and loads the dag-watch LaunchAgent on macOS.

Manual:

1. Copy `skills/dag/SKILL.md` to `~/.grok/skills/dag/SKILL.md`
2. Copy `tools/dag-switch.sh` to `~/.grok/tools/dag-switch.sh` and make executable
3. Symlink: `ln -s ~/.grok/tools/dag-switch.sh ~/.local/bin/dag`
4. Copy `tools/dag-presets/*.toml` to `~/.grok/config-presets/`
5. Copy `tools/dag-health.sh`, `tools/dag-watch.sh`, `tools/dag-watch-daemon.sh` to `~/.grok/tools/`
6. Install the LaunchAgent for health monitoring (optional):
   ```bash
   cp com.michaelnichols.dag-health.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.michaelnichols.dag-health.plist
   ```
7. `dag-watch on` for real-time failure banners

## Troubleshooting

**"dag: command not found"** — The `dag` symlink isn't in `$PATH`. Run:
```bash
ln -s ~/.grok/tools/dag-switch.sh ~/.local/bin/dag
```

**TUI shows old models after switch** — You must restart the TUI. Config binds at
session start only. Quit fully (Cmd+Q) and open from a fresh terminal.

**Provider 401s after switch** — Run `dag-health.sh` to check if API keys are
missing from the TUI process environment. Restart grok from a shell that sourced
`~/.zshrc`.
