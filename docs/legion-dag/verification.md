# Verification Evidence (2026-07-31)

End-to-end verification that the DAG is fully functional: every API key, every
role, every model slot, plus the orchestrator dispatch proof.

## 1. API keys

All three provider keys were checked three ways:

| Check | Result |
|---|---|
| Present in the TUI process environment | PASS — all three (`ps -ww -p <pid> -E`) |
| Match the single source of truth (`~/.grok/credentials.toml`) | PASS — masked fingerprints identical |
| Live authentication against the provider API | PASS — HTTP 200 for each |

Live probes: DeepSeek (`deepseek-chat` and `deepseek-v4-pro`), Anthropic
(`claude-sonnet-4-5`), OpenAI (`gpt-4o-mini`, plus the DAG models below).
`XAI_API_KEY` is intentionally absent.

## 2. Role → model → provider proof matrix

Every role proven by completing a real subagent task in the active session
(`subagent model resolved` entries in the session log all carried
`priority: config_override` and the correct provider key prefix):

| Role | Model | Provider | Proof |
|---|---|---|---|
| explore | deepseek-v4-flash | DeepSeek | completed config/log audit |
| architect | deepseek-v4-flash | DeepSeek | completed log-rotation design |
| general-purpose | deepseek-v4-flash | DeepSeek | completed key tests + model probes |
| plan | claude-opus-5 | Anthropic | completed watcher-fix plan |
| implementor | claude-opus-5 | Anthropic | completed probe task |
| verifier | gpt-5.6-sol | OpenAI | completed config verification + fix review |
| orchestrator | deepseek-v4-pro | DeepSeek | direct API probe HTTP 200 (role not spawnable; the main agent serves it) |

Fallback slots were also probed directly: `gpt-5.6-luna` → HTTP 200 on the
OpenAI Responses API; `deepseek-v4-pro` → HTTP 200. Every one of the 14
configured slots (7 primary + 7 fallback) maps to a model that has either
completed a real task or returned HTTP 200.

## 3. Orchestrator proof — correct dispatch is the function

Delegation is the orchestrator's entire job, so correct subagent spawning IS
the functional proof. In the active session:

- 32 subagent resolutions, every one resolving to the Config B matrix
  (role → model → provider → key prefix all correct).
- **Zero inference failures since the session began**; the 5 failures in the
  log tail all predate the session (previous TUI instance, pre-fix request
  shapes at 13:28–13:32 local).

## 4. Known caveats

1. The main (orchestrator-serving) agent runs as `deepseek-v4-flash`
   (`[models] default`), not `deepseek-v4-pro`. The `orchestrator →
   deepseek-v4-pro` matrix entry is configured but not exercised because
   orchestrator-typed subagents are not a spawnable type in the current build.
   `deepseek-v4-pro` itself is verified working (HTTP 200, reasoning-capable).
2. `gpt-5.6-luna` requires `max_output_tokens >= 16` on the Responses API
   (a parameter floor, not a key/model issue).
