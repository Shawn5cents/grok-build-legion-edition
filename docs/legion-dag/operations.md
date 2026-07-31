# Operations

## Health watcher

- **Script:** `~/.grok/tools/dag-health.sh`
- **LaunchAgent:** `com.michaelnichols.dag-health` (60-second interval,
  `RunAtLoad`). Config: `~/Library/LaunchAgents/com.michaelnichols.dag-health.plist`
- **Log:** `~/.grok/logs/dag-health.log`
- **Dismissal state:** `~/.grok/logs/dag-health.last`

### What it checks (every 60s)

1. TUI process environment contains `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`,
   `OPENAI_API_KEY` (missing key → subagents silently 401).
2. Session log, 15-minute lookback: `inference_failed` / Authentication
   failures / Unauthorized (401).
3. Claude/GPT subagent resolutions that used `SessionToken` instead of an API
   key.

### Notification behavior

On a detected problem the watcher raises a **persistent on-screen alert**
(modal critical dialog) that stays until you close it. Closing it marks that
problem class as dismissed — it will not nag again. A new problem class raises
a new alert.

Re-enable alerts for previously dismissed classes:

```sh
: > ~/.grok/logs/dag-health.last
```

Force an immediate run (optional — the 60s tick picks up script edits on its
own):

```sh
launchctl unload ~/Library/LaunchAgents/com.michaelnichols.dag-health.plist && \
launchctl load ~/Library/LaunchAgents/com.michaelnichols.dag-health.plist
```

Disable the watcher entirely:

```sh
launchctl unload ~/Library/LaunchAgents/com.michaelnichols.dag-health.plist
```

## Verifying DAG health by hand

1. **Keys in the TUI process env:**
   ```sh
   ps -ww -p $(pgrep -f xai-grok-pager | head -1) -E | grep -E 'DEEPSEEK_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY' | sed 's/=.*/=<set>/'
   ```
   All three must be present. If not, restart the TUI from a shell that has
   sourced the login profile (which exports the keys via the credentials
   loader) — a long-lived parent shell will not pick up new keys.
2. **Recent failures:**
   ```sh
   tail -c 200000 ~/.grok/logs/unified.jsonl | grep -c inference_failed
   tail -c 200000 ~/.grok/logs/unified.jsonl | grep -ciE 'authentication'
   ```
   Both should be low/zero apart from known historical entries.
3. **Model resolutions:**
   ```sh
   grep -o '"subagent model resolved[^}]*}' ~/.grok/logs/unified.jsonl | tail -6
   ```
   Expect role → model pairs matching the Config B matrix, with real
   provider key prefixes and no `SessionToken` auth.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| 401 "token not from a valid issuer" / "Invalid API Key" | key missing from TUI process env; subagent fell back to session JWT | restart TUI from a fresh shell that sources the login profile; verify with `ps -ww -p <pid> -E` |
| 400 "anthropic-version: header is required" | static header placed in `env_http_headers` (silently dropped) | must live in `extra_headers` (Fix 1/2 pattern in `config.toml`) |
| 400 "Function tools with reasoning_effort are not supported" | OpenAI models on chat/completions backend | `api_backend = "responses"` for gpt models |
| 400 `max_output_tokens` below minimum | Responses API floor (16) | use ≥ 16 |
| Watcher dies with `unbound variable` | malformed state line under `set -u` | state lines are now pruned before evaluation; if it recurs, reset `~/.grok/logs/dag-health.last` |
| Alerts re-nag every 2 minutes | old timestamp-dedupe behavior | current build is dismissal-based; reset state file if needed |

## Credentials

- Single source of truth: `~/.grok/credentials.toml` (`[providers.deepseek]`,
  `[providers.anthropic]`, `[providers.openai]`).
- The login profile derives exports from it via the credentials loader —
  never hardcode keys in the profile.
- `XAI_API_KEY` is intentionally not set (grok out of the DAG).

## DAG config changes

`config.toml` binds at session start. To change the DAG:

1. Edit `~/.grok/config.toml` (back it up first: `cp config.toml config.toml.bak-$(date +%Y%m%d-%H%M%S)`).
2. Restart the TUI from a fresh terminal.
3. Verify: keys in env, then a test subagent per affected provider.
4. If changing the active preset: keep `~/.grok/config-presets/best-value-dag.toml` in sync (all five provider blocks must match).
