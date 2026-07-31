# Local DAG Configuration Snapshot

This file describes one noncanonical configuration stored in
`~/.grok/config.toml` on 2026-07-31. It differs from the repository-owned
[`presets/legion-dag.toml`](../../../presets/legion-dag.toml). Do not treat this
snapshot as the default configuration for other Legion installations.

The tested build loaded this configuration at session start, so a TUI restart
was required after changes.

## Role to model matrix

### Primary (`[subagents.models]`)

| Role | Model | Provider |
|---|---|---|
| orchestrator | `deepseek-v4-pro` | DeepSeek |
| explore | `deepseek-v4-flash` | DeepSeek |
| architect | `deepseek-v4-flash` | DeepSeek |
| general-purpose | `deepseek-v4-flash` | DeepSeek |
| plan | `claude-opus-5` | Anthropic |
| implementor | `claude-opus-5` | Anthropic |
| verifier | `gpt-5.6-sol` | OpenAI |

### Fallbacks (`[subagents.fallback]`)

| Role | Model | Provider |
|---|---|---|
| orchestrator | `claude-opus-5` | Anthropic |
| explore | `gpt-5.6-luna` | OpenAI |
| plan | `gpt-5.6-sol` | OpenAI |
| architect | `claude-opus-5` | Anthropic |
| implementor | `deepseek-v4-pro` | DeepSeek |
| verifier | `deepseek-v4-pro` | DeepSeek |
| general-purpose | `gpt-5.6-luna` | OpenAI |

The local operator selected different primary providers for implementor and
verifier so one provider outage would not remove both roles at once. This is a
deployment choice, not a runtime guarantee or a project default.

## Provider and authentication settings

| Models | Base URL | Authentication environment variable | Backend | Notes |
|---|---|---|---|---|
| `deepseek-v4-pro`, `deepseek-v4-flash` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` | Chat Completions | Local override |
| `claude-opus-5` | `https://api.anthropic.com/v1` | `ANTHROPIC_API_KEY` | Messages | `x-api-key` from the environment; static `anthropic-version` in `extra_headers` |
| `gpt-5.6-sol`, `gpt-5.6-luna` | `https://api.openai.com/v1` | `OPENAI_API_KEY` | Responses | Local override |

### Credential resolution

For models configured with `env_key` or `env_http_headers`, the tested process
resolved credentials from its environment. If an `env_key` was configured but
unset, the runtime could fall through to session-token authentication, which
was invalid for these third-party endpoints.

Use a presence-only check. Never print or save the raw output of `ps -E`:

```sh
tui_pid="$(pgrep -f xai-grok-pager | head -1)"
if [ -n "$tui_pid" ]; then
  ps -ww -p "$tui_pid" -E |
    awk '{
      for (i = 1; i <= NF; i++) {
        if ($i ~ /^(DEEPSEEK_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY)=/) {
          sub(/=.*/, "=<set>", $i)
          print $i
        }
      }
    }'
fi
```

The expected output contains only variable names followed by `=<set>`.

## Main-session model

The local `[models] default` was `deepseek-v4-flash`. Although the subagent
matrix mapped `orchestrator` to `deepseek-v4-pro`, an orchestrator-typed
subagent was not spawnable in the tested build. A direct API probe established
model availability only; it did not exercise orchestrator dispatch.

## Local presets

The machine also contained two files under `~/.grok/config-presets/`:

- `best-value-dag.toml`, a local copy of this snapshot.
- `deepseek-cost-dag.toml`, a local rollback option.

Neither file is included in this case study. Repository users should prefer
the versioned presets under [`presets/`](../../../presets/).
