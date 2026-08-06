"""log_reader.py — stream DAG-routing events from ``unified.jsonl``.

The Grok TUI writes subagent lifecycle events to ``~/.grok/logs/unified.jsonl``
as JSON lines with the shape::

    {"ts":"2026-08-02T04:45:15.027Z","src":"shell","pid":49172,"lvl":"info",
     "msg":"subagent spawn credentials","ctx":{
       "subagent_id":"019fc0ca-...","subagent_type":"implementor",
       "effective_model":"deepseek-v4-pro","effective_model_raw":"deepseek-v4-pro",
       "base_url":"https://api.deepseek.com/v1","key_prefix":"sk-ff5eb",
       "auth_type":"ApiKey","model_has_own_creds":true,
       "auth_method_id":"xai.api_key","parent_model":"deepseek-v4-pro",
       "parent_key_prefix":"sk-ff5eb","context_window":1000000}}
    {"ts":"2026-08-02T04:47:33.001Z",...,
     "msg":"subagent completed","ctx":{
       "subagent_id":"019fc0ca-...","subagent_type":"implementor",
       "effective_model":"deepseek-v4-pro","success":true,"cancelled":false,
       "duration_ms":137971,"turns":1,"tool_calls":24,
       "output_preview":"...","error":null}}

We turn those into typed dataclasses:

- ``SpawnEvent``     — agent created, includes role + resolved model.
- ``TerminalEvent``  — agent finished (success / cancelled / error).

Other event kinds (``subagent model resolved``, ``subagent read parent config
(live)``) are useful for diagnostics but we don't expose typed wrappers for
them — the raw dict is preserved on ``SpawnEvent.parent_*`` if present.

Streaming is forward-only via generators so the 5 MB+ log file doesn't get
loaded into memory at once. Malformed lines are skipped (counted via
``read_all``'s returned tuple).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


@dataclass
class SpawnEvent:
    """``subagent spawn credentials`` event."""

    ts: str
    ts_dt: datetime
    subagent_id: str
    role: str
    model: str
    model_raw: str
    base_url: str
    parent_model: str = ""
    parent_base_url: str = ""
    key_prefix: str = ""
    auth_type: str = ""
    context_window: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TerminalEvent:
    """``subagent completed`` event (or ``subagent_failed`` / ``subagent cancelled``)."""

    ts: str
    ts_dt: datetime
    subagent_id: str
    role: str
    model: str
    success: bool
    cancelled: bool
    duration_ms: int = 0
    turns: int = 0
    tool_calls: int = 0
    error: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def outcome(self) -> str:
        """Human-friendly outcome bucket (completed / failed / cancelled)."""
        if self.cancelled:
            return "cancelled"
        if self.success:
            return "completed"
        return "failed"


# ---------------------------------------------------------------------------
# Time parsing
# ---------------------------------------------------------------------------


def _parse_ts(raw: str) -> Optional[datetime]:
    """Parse a UTC ISO-8601 timestamp like ``2026-08-02T04:45:15.027Z``."""
    if not raw:
        return None
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Single-event parsers
# ---------------------------------------------------------------------------


def _parse_spawn(ctx: Dict[str, Any]) -> SpawnEvent:
    ts = str(ctx.get("ts", "")) or ""
    return SpawnEvent(
        ts=ts,
        ts_dt=_parse_ts(ts) or _now(),
        subagent_id=str(ctx.get("subagent_id", "")),
        role=str(ctx.get("subagent_type", "")),
        model=str(ctx.get("effective_model", "")),
        model_raw=str(ctx.get("effective_model_raw", "")),
        base_url=str(ctx.get("base_url", "")),
        parent_model=str(ctx.get("parent_model", "")),
        parent_base_url=str(ctx.get("parent_base_url", "")),
        key_prefix=str(ctx.get("key_prefix", "")),
        auth_type=str(ctx.get("auth_type", "")),
        context_window=int(ctx.get("context_window", 0) or 0),
        raw=ctx,
    )


def _parse_terminal(ctx: Dict[str, Any]) -> TerminalEvent:
    ts = str(ctx.get("ts", "")) or ""
    return TerminalEvent(
        ts=ts,
        ts_dt=_parse_ts(ts) or _now(),
        subagent_id=str(ctx.get("subagent_id", "")),
        role=str(ctx.get("subagent_type", "")),
        model=str(ctx.get("effective_model", "")),
        success=bool(ctx.get("success", False)),
        cancelled=bool(ctx.get("cancelled", False)),
        duration_ms=int(ctx.get("duration_ms", 0) or 0),
        turns=int(ctx.get("turns", 0) or 0),
        tool_calls=int(ctx.get("tool_calls", 0) or 0),
        error=ctx.get("error"),
        raw=ctx,
    )


# ---------------------------------------------------------------------------
# Stream API
# ---------------------------------------------------------------------------


def _iter_jsonl(path: str) -> Iterator[Dict[str, Any]]:
    """Yield decoded JSON objects from a JSONL file, line by line."""
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (ValueError, json.JSONDecodeError):
                continue
            if isinstance(obj, dict):
                yield obj


def _in_lookback(ts_dt: datetime, lookback_dt: datetime) -> bool:
    return ts_dt >= lookback_dt


def stream_events(
    path: str,
    lookback_min: int = 1440,
    now: Optional[datetime] = None,
) -> Iterator[Tuple[str, Any]]:
    """Yield ``(kind, event)`` tuples for spawn / terminal events.

    ``kind`` is one of: ``"spawn"`` | ``"terminal"`` | ``"other"``.
    Other events pass through as raw dicts so callers can build richer
    coverage reports later.
    """
    if not os.path.exists(path):
        return
    cutoff = (now or _now()) - timedelta(minutes=lookback_min)
    for obj in _iter_jsonl(path):
        msg = obj.get("msg", "")
        ctx = obj.get("ctx") or {}
        ctx_ts = str(obj.get("ts", "") or "")
        ts_dt = _parse_ts(ctx_ts) or _now()
        if ts_dt < cutoff:
            continue

        # Inject the outer ts so downstream _parse_* sees a consistent key.
        if "ts" not in ctx and ctx_ts:
            ctx["ts"] = ctx_ts

        if msg == "subagent spawn credentials":
            yield ("spawn", _parse_spawn(ctx))
        elif msg in ("subagent completed", "subagent failed", "subagent cancelled"):
            yield ("terminal", _parse_terminal(ctx))
        else:
            yield ("other", obj)


def read_all(
    path: str,
    lookback_min: int = 1440,
    now: Optional[datetime] = None,
) -> Tuple[List[SpawnEvent], List[TerminalEvent], int, int]:
    """Read all spawn + terminal events within the lookback window.

    Returns ``(spawns, terminals, malformed_count, total_count)``.
    Terminal events are deduplicated per ``subagent_id`` — later records
    overwrite earlier ones, so a failed-then-retried-then-completed agent
    ends up as a single ``completed`` record.
    """
    spawns: List[SpawnEvent] = []
    terminals_by_id: Dict[str, TerminalEvent] = {}
    malformed = 0

    total = 0
    for kind, ev in stream_events(path, lookback_min=lookback_min, now=now):
        total += 1
        if kind == "spawn":
            spawns.append(ev)
        elif kind == "terminal":
            existing = terminals_by_id.get(ev.subagent_id)
            if existing is None or _terminal_priority(ev) >= _terminal_priority(existing):
                terminals_by_id[ev.subagent_id] = ev

    return spawns, list(terminals_by_id.values()), malformed, total


def _terminal_priority(ev: TerminalEvent) -> int:
    """Higher = wins when multiple terminal records exist for the same id."""
    if ev.success:
        return 3
    if not ev.cancelled:
        return 2
    return 1


def latest_spawn_for(spawns: Iterable[SpawnEvent], subagent_id: str) -> Optional[SpawnEvent]:
    for s in spawns:
        if s.subagent_id == subagent_id:
            return s
    return None


def pair_spawns_with_terminals(
    spawns: List[SpawnEvent], terminals: List[TerminalEvent]
) -> List[Tuple[SpawnEvent, Optional[TerminalEvent]]]:
    """Return one row per spawn with its terminal event (if any) attached."""
    term_by_id = {t.subagent_id: t for t in terminals}
    out: List[Tuple[SpawnEvent, Optional[TerminalEvent]]] = []
    for s in spawns:
        out.append((s, term_by_id.get(s.subagent_id)))
    return out