# DAG Configuration — Config B (hardened v3, 2026-07-31)

The active DAG configuration lives in `~/.grok/config.toml`. It binds at
session start — changing it requires a TUI restart.

## Role → model matrix

### Primary (`[subagents.models]`)

| Role | Model | Provider |
|---|---|---|
| orchestrator | `deepseek-v4-pro` | DeepSeek |
| explore | `deepseek-v4-flash` | DeepSeek |
| architect | `deepseek-v4-flash` | DeepSeek |
| general-purpose | `deepseek-v4-flash` | DeepSeek |
| plan | `claude-opus-5` | Anthropic |
| implementor | `claude-opus-5` | Anthropic |
| verifier | `gpt-5.6-sol` | OpenAI (cross-family from implementor, by design) |

### Fallbacks (`[subagents.fallback]` — single level per role)

| Role | Model | Provider |
|---|---|---|
| orchestrator | `claude-opus-5` | Anthropic |
| explore | `gpt-5.6-luna` | OpenAI (cross-vendor: a DeepSeek outage must not kill explore) |
| plan | `gpt-5.6-sol` | OpenAI |
| architect | `claude-opus-5` | Anthropic |
| implementor | `deepseek-v4-pro` | DeepSeek |
| verifier | `deepseek-v4-pro` | DeepSeek (cross-family with implementor in every single-vendor failure) |
| general-purpose | `gpt-5.6-luna` | OpenAI |

### Cross-family guarantee

implementor → claude-opus-5 (Anthropic) and verifier → gpt-5.6-sol (OpenAI) are
deliberately different vendors, so a single-vendor outage cannot take out both
the implementor and its verifier. The verifier fallback is `deepseek-v4-pro`,
keeping implementor + verifier cross-family under every single-vendor failure.

## Provider / auth settings

| Models | Base URL | Auth (env) | Backend | Notes |
|---|---|---|---|---|
| `deepseek-v4-pro`, `deepseek-v4-flash` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` | chat/completions | — |
| `claude-opus-5` | `https://api.anthropic.com/v1` | `ANTHROPIC_API_KEY` | messages | `x-api-key` header from env; static `anthropic-version: 2023-06-01` via extra_headers |
| `gpt-5.6-sol`, `gpt-5.6-luna` | `https://api.openai.com/v1` | `OPENAI_API_KEY` | responses | Responses API (`api_backend = "responses"`) |

### Auth sourcing rule (critical)

Model keys resolve from the **TUI process environment**
(`env_key` / `env_http_headers`), **not** from `credentials.toml` directly.
If a key is missing from the TUI process, that provider's subagents silently
fall back to the session JWT and 401 — the DAG looks healthy but never calls
the provider. Always launch the TUI from a shell that has sourced the login
profile (which exports `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY` via the credentials loader). A long-lived parent shell that
predates new keys will not pick them up — restart the TUI from a fresh terminal
after adding/rotating keys.

Verify: `ps -ww -p <tui-pid> -E | grep API_KEY`

## Main-session model

`[models] default = "deepseek-v4-flash"` — the main (orchestrator-serving)
agent runs on this model. The `orchestrator → deepseek-v4-pro` entry in the
subagents matrix applies only if an orchestrator-typed subagent can be spawned
(not a spawnable type in the current build), so in practice the orchestrator
runs on the default. `deepseek-v4-pro` itself is verified working and remains
the fallback for implementor/verifier.

## What is intentionally NOT configured

- **No `[providers.xai]` section** — grok is intentionally out of the DAG
  (free-tier limits).
- **No kilo gateway** — the `api.kilo.ai` / `openrouter/free` / `nemotron:free`
  model definitions were removed 2026-07-31; only removal-notice comments
  remain.

## Presets

`~/.grok/config-presets/`:
- `best-value-dag.toml` — the active config (synced 2026-07-31, including
  provider auth settings; model matrix identical to Config B).
- `deepseek-cost-dag.toml` — cost-savings rollback (one-file swap into
  `config.toml`, then restart the session).

Backups of `config.toml` from the 07-31 session are kept alongside as
`.bak-YYYYMMDD-HHMMSS` files.
