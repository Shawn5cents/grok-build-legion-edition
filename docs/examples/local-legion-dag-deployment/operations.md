# Example Local Operations

These commands describe the macOS deployment in this case study. Adapt and
review them before use; Legion does not install the watcher described here.

## Local watcher layout

- Script: `~/.grok/tools/dag-health.sh`
- Example LaunchAgent label: `com.example.legion-dag-health`
- Example property list:
  `~/Library/LaunchAgents/com.example.legion-dag-health.plist`
- Log: `~/.grok/logs/dag-health.log`
- Local dismissal state: `~/.grok/logs/dag-health.last`

The recorded watcher ran every 60 seconds and checked:

1. Whether the TUI process had the three configured provider variables.
2. Whether recent session logs contained selected authentication or inference
   failures.
3. Whether Claude or GPT model resolutions unexpectedly used session-token
   authentication.

The watcher source is not included, and its sticky dismissal behavior has a
known recurrence-detection limitation described in [`fixes.md`](fixes.md).

## Safe credential-presence check

Do not run `ps -E | grep API_KEY`: it prints credential values. This example
emits only allowlisted variable names and replaces every value with `<set>`:

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

Expected output:

```text
DEEPSEEK_API_KEY=<set>
ANTHROPIC_API_KEY=<set>
OPENAI_API_KEY=<set>
```

Never paste raw process-environment output into an issue, pull request, log,
or chat.

## Log inspection

The following counts matching entries in a bounded tail. It does not establish
when the events occurred, so inspect timestamps before deciding an incident is
active:

```sh
tail -c 200000 ~/.grok/logs/unified.jsonl | grep -c inference_failed
tail -c 200000 ~/.grok/logs/unified.jsonl | grep -ci authentication
```

## Example LaunchAgent control

Replace the example label and path with values from the local property list:

```sh
launchctl kickstart -k "gui/$(id -u)/com.example.legion-dag-health"
launchctl print "gui/$(id -u)/com.example.legion-dag-health"
```

To remove an installed example agent from the current GUI domain:

```sh
launchctl bootout \
  "gui/$(id -u)" \
  ~/Library/LaunchAgents/com.example.legion-dag-health.plist
```

## Troubleshooting notes from this deployment

| Symptom | Reported local cause | Follow-up |
|---|---|---|
| 401 invalid-token response | Intended provider key absent from the TUI environment | Restart from a shell with the required variable, then use the redacted presence check above. |
| Missing Anthropic version header | Static header placed in an environment-header mapping | Put the nonsecret static value in `extra_headers`; keep the secret key environment-backed. |
| OpenAI tool/reasoning request rejected | Local model override used Chat Completions | Use the backend required by that model and verify against current provider documentation. |
| Watcher exits under `set -u` | Malformed local state | Validate state before evaluation and test the actual script. |
| Recurring incident stays silent | Sticky dismissal state | Confirm health, reset state, and replace sticky dismissal with transition-based alerting. |

## Configuration changes

Back up local configuration, make the smallest change, restart the TUI if the
tested build requires it, and validate only the affected provider and roles.
Do not copy this case study's model matrix over a repository preset.
