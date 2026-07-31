# Local Legion DAG Deployment Case Study

This directory records one macOS deployment of Legion as it existed on
2026-07-31. It is an operational case study, not the project's canonical DAG
configuration, an installer, or a support contract. The paths, model choices,
presets, watcher, and validation results described here may not exist on other
machines.

For project-owned configuration, use:

- [`presets/legion-dag.toml`](../../../presets/legion-dag.toml)
- [`HETEROGENEOUS_AGENTS.md`](../../../HETEROGENEOUS_AGENTS.md)

## Contents

| File | Contents |
|---|---|
| `dag-configuration.md` | Snapshot of the local role, model, fallback, and provider configuration |
| `2026-07-31-incident.md` | Local incident timeline and reported root causes |
| `fixes.md` | Local changes and remaining monitoring limitation |
| `verification.md` | Timestamped local validation record and its limits |
| `model-research.md` | Source-backed DeepSeek V4 release notes relevant to this deployment |
| `operations.md` | Example health checks and troubleshooting guidance |

## Recorded status

- Six spawnable roles completed local tasks.
- The configured orchestrator model returned HTTP 200, but an
  orchestrator-typed subagent was not exercised because that role was not
  spawnable in the tested build.
- Three provider credentials were reported present and live-authenticating.
- The local watcher was reported running on a 60-second cadence.

These are historical observations from one machine. The underlying session
logs, private configuration, credentials, and watcher script are not part of
this repository, so the claims are not independently reproducible from this
commit alone.

## Security note

No API keys, tokens, passwords, masked key fingerprints, session identifiers,
private addresses, or user-specific LaunchAgent labels are stored here.
Commands that inspect a process environment must redact values before printing
or saving output.
