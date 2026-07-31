# Local Changes Recorded on 2026-07-31

The files described here lived outside this repository. This document records
what the local operator reported changing; it is not a reviewable patch or
proof that the same changes are appropriate for another installation.

## Provider override corrections

The local `~/.grok/config.toml` and a local rollback preset were reported
updated as follows:

- Anthropic requests used the Messages backend, obtained `x-api-key` from the
  environment, and stored the static `anthropic-version` value in
  `extra_headers`.
- OpenAI models used the Responses backend.
- DeepSeek models continued to resolve `DEEPSEEK_API_KEY` against the direct
  API endpoint.

The private files are not included, so byte-for-byte equality between the
active configuration and rollback preset cannot be verified from this commit.

## Watcher state handling

The local `~/.grok/tools/dag-health.sh` was reported changed to:

- reject malformed or whitespace-containing state entries before evaluation;
- avoid arithmetic on untrusted state-file content;
- write state through a temporary file followed by `mv`; and
- pass alert text to AppleScript through arguments rather than interpolation.

The script itself is not included in this case study. These implementation
claims should not be copied into another watcher without reviewing and testing
the actual script.

## Known monitoring limitation

The local watcher recorded a failure class after its alert was dismissed and
suppressed that class until the state file was manually reset. That prevents a
nag loop, but it can also hide a later recurrence of the same incident.

A production watcher should instead model state transitions:

1. Alert when a class changes from healthy to failing.
2. Suppress repeats while the same failure remains active.
3. Clear the active state after a confirmed healthy observation.
4. Alert again if the class later changes back to failing.

Until the local watcher implements that lifecycle, reset its dismissal state
only after confirming that the underlying problem is healthy:

```sh
: > ~/.grok/logs/dag-health.last
```

## Deferred log rotation

The operator noted that `~/.grok/logs/dag-health.log` could grow without bound.
No rotation change was included or validated in this case study.
