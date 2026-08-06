---
name: dag
description: "/dag status | full | mixed | economy | list — switch between Legion DAG presets or check status. Restart TUI after switching."
metadata:
  short-description: "/dag status | full | mixed | economy | list"
  user-invocable: true
---

# DAG Preset Switcher

The user wants to check or change their DAG (Directed Acyclic Graph) preset for Grok Build.

## Available commands

| User says | Action |
|---|---|
| `/dag`, `/dag status` | Run `dag status` — show current preset |
| `/dag full` | Run `dag full` — switch to flagship multi-vendor |
| `/dag mixed` | Run `dag mixed` — switch to multi-family economy |
| `/dag economy` | Run `dag economy` — switch to DeepSeek-primary |
| `/dag list` | Run `dag list` — show all available presets |

## Procedure

1. Determine which variant the user wants (if unclear, run `dag status` to show current state)
2. Run the corresponding shell command: `dag <variant>`
3. Display the output

## After switching presets

IMPORTANT: After ANY switch (full, mixed, economy), remind the user:

> ⚠️ **Restart required.** The Grok TUI binds config at session start.
> Quit fully (Cmd+Q or `/quit`), open a fresh terminal, and run `grok`.

The switch has been written to disk and will take effect on next launch.

## Never

- Never switch without the user explicitly choosing a preset (full, mixed, or economy)
- Never restart the TUI or tell the user to `exec` their shell — just remind them to quit and reopen
