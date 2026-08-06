"""dag_inspector — inspect, diff, validate, audit the Grok DAG ecosystem.

A small CLI that reads ~/.grok/config.toml (active DAG), the preset files
under ~/.grok/config-presets/, and the unified.jsonl log to give operators
visibility into what model each subagent role is currently routed to, what
fallbacks exist, whether the API keys for those providers are set, and how
the active DAG compares against other presets or historical backups.

Stdlib-only. Python 3.9+ compatible.
"""

__version__ = "0.1.0"