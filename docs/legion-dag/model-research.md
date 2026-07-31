# Model Research: DeepSeek V4-Flash (2026-07-31)

Research performed 2026-07-31 via keyless web search against DeepSeek's
official changelog, HuggingFace, and independent tech press.

## Release

- `deepseek-v4-flash` (build **0731**) entered **public beta on the DeepSeek
  API on 2026-07-31** — official changelog: "DeepSeek-V4-Flash Update …
  simply set the model name to `deepseek-v4-flash` … keeps the same model
  architecture and size as DeepSeek-V4-Flash-Preview, re-post-trained."
- HuggingFace `deepseek-ai/DeepSeek-V4-Flash-0731` created 2026-07-31
  (07:30 UTC), MIT license.
- Covered same-day by TechNode and TechTimes.
- The V4 family was originally previewed 2026-04-24; this is the official
  Flash API release.

## Ranking: Flash vs Pro

| | V4-Flash (0731) | V4-Pro (Preview only) |
|---|---|---|
| Tier | agent-optimized / budget | **flagship** (1.6T total / 49B active params) |
| Agent benchmarks | **beats Pro-Preview on all nine** — Terminal Bench 2.1 82.7, DeepSWE 54.4, Cybergym 76.7, Toolathlon 70.3, NL2Repo 54.2 | trails Flash on agent scores |
| General/coding/reasoning | strong | flagship for these |
| Price per 1M tokens | $0.14 in / $0.28 out | $0.435 / $0.87 |
| Release status | released 2026-07-31 (public beta) | official release "will follow soon" |

Takeaway: Flash-0731 is currently DeepSeek's strongest **agent** model
(exactly what a tool-calling DAG runs on) and far cheaper; Pro-Preview remains
the flagship tier for raw general capability until the official Pro ships.

## Fit with the DAG

- `deepseek-v4-flash` runs the high-volume agentic roles (explore, architect,
  general-purpose) — strongest + cheapest agent model, released the same day
  Config B was hardened.
- `deepseek-v4-pro` sits on orchestrator / implementor-verifier fallbacks —
  the flagship-tier (preview) model for planning-heavy roles.
- Beta caveat: Flash-0731 is public beta; live probes in this session
  (including `deepseek-v4-pro`) all returned clean HTTP 200.
