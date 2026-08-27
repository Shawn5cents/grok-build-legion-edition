---
name: dag
description: "Switch Legion DAG presets (status | full | mixed | economy | list). /dag alone shows help."
argument-hint: "status | full | mixed | economy | list"
user-invocable: true
metadata:
  short-description: "/dag status | full | mixed | economy | list"
---

# DAG Preset Switcher

The user wants to check or change their DAG (Directed Acyclic Graph) preset for Grok Build.

## `/dag` with no arguments — SHOW HELP, do NOT run anything

If the user types `/dag` alone (no arguments), do NOT run any shell command and do NOT switch presets. Present the help prompt:

> **DAG preset switcher** — choose one:
>
> | Command | Action |
> |---|---|
> | `/dag status` | Show current preset |
> | `/dag full` | Switch to flagship multi-vendor |
> | `/dag mixed` | Switch to multi-family economy |
> | `/dag economy` | Switch to DeepSeek-primary (default, low cost) |
> | `/dag list` | Show all available presets |

Then ask which variant they want.

## Available commands

| User says | Action |
|---|---|
| `/dag status` | Run `dag status` — show current preset |
| `/dag full` | Run `dag full` — switch to flagship multi-vendor |
| `/dag mixed` | Run `dag mixed` — switch to multi-family economy |
| `/dag economy` | Run `dag economy` — switch to DeepSeek-primary |
| `/dag list` | Run `dag list` — show all available presets |

## Procedure

1. If no arguments were given, show the help prompt above and ask which variant the user wants
2. Determine which variant the user wants (if still unclear, run `dag status` to show current state)
3. Run the corresponding shell command: `dag <variant>`
4. Display the output

## After switching presets

IMPORTANT: After ANY switch (full, mixed, economy), remind the user:

> ⚠️ **Restart required.** The Grok TUI binds config at session start.
> Quit fully (Cmd+Q or `/quit`), open a fresh terminal, and run `grok`.

The switch has been written to disk and will take effect on next launch.

## Never

- Never switch without the user explicitly choosing a preset (full, mixed, or economy)
- Never run a command when `/dag` was typed with no arguments — show the help prompt instead
- Never restart the TUI or tell the user to `exec` their shell — just remind them to quit and reopen
