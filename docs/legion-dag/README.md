# Legion DAG Configuration — Documentation

This directory documents the **multi-agent DAG configuration** of the Legion
CLI: the configuration itself (Config B, hardened v3, 2026-07-31), the
07-31 incident and its fixes, the full verification evidence, model research,
and day-to-day operations.

## Contents

| File | Contents |
|---|---|
| `dag-configuration.md` | The active DAG config: role → model matrix, fallbacks, provider/auth settings, presets |
| `2026-07-31-incident.md` | Timeline of the 07-31 failures and their root causes |
| `fixes.md` | Every fix applied: preset sync, watcher rewrite, notification behavior change, docs |
| `verification.md` | End-to-end verification: API keys, role-model-provider proofs, model probes |
| `model-research.md` | DeepSeek V4-Flash release research (2026-07-31) |
| `operations.md` | Health checks, reload, reset, troubleshooting |

## Quick status (2026-07-31)

- **DAG configuration**: Config B (hardened v3) — verified exact match.
- **API keys**: all three providers (DeepSeek, Anthropic, OpenAI) present in
  the TUI process environment, matching the single source of truth, and
  live-authenticated (HTTP 200).
- **Roles**: all seven roles and five model slots proven working end-to-end.
- **Watcher**: fixed and running on a 60-second cadence with persistent-alert
  notification behavior.

## Security note

**No secrets are stored in these documents.** No API keys, tokens, passwords,
or private addresses. Provider credentials live only in `~/.grok/credentials.toml`
(single source of truth) and are exported into the shell environment at login.
References to credentials are by environment-variable name only.
