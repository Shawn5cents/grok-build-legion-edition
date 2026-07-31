# Local Validation Record

This is a timestamped report from one deployment on 2026-07-31. The private
session logs, configuration, and credentials are intentionally absent, so the
results cannot be independently reproduced from the repository.

## Provider checks reported by the operator

For DeepSeek, Anthropic, and OpenAI, the operator reported:

- the configured environment variable was present in the TUI process;
- its value matched the local credential source; and
- a provider request returned HTTP 200.

No key values or masked key fingerprints are included here. An HTTP 200 proves
that one request authenticated at that time; it does not prove every configured
role, request shape, or fallback path.

## Exercised roles

Six spawnable roles reportedly completed a task in the observed session:

| Role | Model | Reported task |
|---|---|---|
| explore | `deepseek-v4-flash` | Configuration and log audit |
| architect | `deepseek-v4-flash` | Log-rotation design |
| general-purpose | `deepseek-v4-flash` | Provider and model probes |
| plan | `claude-opus-5` | Watcher-fix plan |
| implementor | `claude-opus-5` | Probe task |
| verifier | `gpt-5.6-sol` | Configuration review |

The configured `orchestrator` model, `deepseek-v4-pro`, returned HTTP 200 in a
direct API probe. An orchestrator-typed subagent was not spawnable in the
tested build, so this did not exercise the orchestrator role or dispatch path.

## What was not proven

- The `orchestrator` role did not complete an end-to-end subagent task.
- Fallback transitions were not induced and observed for every role.
- The repository's canonical `presets/legion-dag.toml` was not under test.
- The local watcher source and its behavior were not added to the repository.
- The observations do not establish future availability or correctness.

The operator also reported 32 matching subagent-resolution log entries and no
new inference failures during the final observation window. Because the logs
are private and ephemeral, those counts are historical context rather than
repository-level verification evidence.
