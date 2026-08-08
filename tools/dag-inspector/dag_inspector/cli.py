"""cli.py — argparse wiring + subcommand dispatch for dag-inspector.

Exit codes:
    0  healthy
    1  warnings (e.g. unset env keys, missing models)
    2  errors   (e.g. malformed config, missing file)
    3  invalid usage

Subcommands:
    runtime     show active DAG routing
    diff        compare two configs
    validate    sanity-check a config
    coverage    runtime coverage from logs
    history     walk .bak files for switch timeline
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import formatting, paths
from .config import load_active, load_file_or_preset


# Exit codes
EXIT_OK = 0
EXIT_WARN = 1
EXIT_ERR = 2
EXIT_USAGE = 3


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dag-inspector",
        description="Inspect, diff, validate, audit the Grok DAG ecosystem.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__()}")
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of pretty-printed tables.",
    )
    p.add_argument(
        "--lookback",
        type=int,
        default=1440,
        help="Lookback window in minutes for log-driven commands (default: 1440 = 24h).",
    )
    p.add_argument(
        "--grok-home",
        default=None,
        help="Override GROK_HOME (default: $GROK_HOME or ~/.grok).",
    )
    sub = p.add_subparsers(dest="command")

    sub.add_parser("runtime", help="Show the active DAG routing.")

    diff_p = sub.add_parser("diff", help="Compare two configs.")
    diff_p.add_argument("source", help="First config (file path or label/alias).")
    diff_p.add_argument("target", help="Second config (file path or label/alias).")

    val_p = sub.add_parser("validate", help="Sanity-check a config.")
    val_p.add_argument(
        "target",
        nargs="?",
        default="active",
        help="Config to validate: file path, label/alias, or 'active' (default).",
    )

    cov_p = sub.add_parser("coverage", help="Runtime coverage from unified.jsonl.")
    cov_p.add_argument(
        "--include-config",
        default="active",
        help="Config to compare against (file path, label/alias, or 'active').",
    )

    his_p = sub.add_parser("history", help="Walk config.toml.bak-* timeline.")
    his_p.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of backup entries to show (default: 20).",
    )

    return p


def __version__() -> str:
    from . import __version__

    return __version__


def _resolve_grok_home(args: argparse.Namespace) -> str:
    home = args.grok_home or paths.grok_home()
    # Export so child imports see the same GROK_HOME if they look it up.
    import os
    os.environ["GROK_HOME"] = home
    return home


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return EXIT_USAGE

    home = _resolve_grok_home(args)

    if args.command == "runtime":
        return _dispatch_runtime(args)
    if args.command == "diff":
        return _dispatch_diff(args)
    if args.command == "validate":
        return _dispatch_validate(args)
    if args.command == "coverage":
        return _dispatch_coverage(args)
    if args.command == "history":
        return _dispatch_history(args)

    parser.print_help()
    return EXIT_USAGE


def _dispatch_runtime(args: argparse.Namespace) -> int:
    from .cmd_runtime import build_runtime_view, render_runtime

    cfg = load_active()
    if args.json:
        print(formatting.to_json(build_runtime_view(cfg)))
        return EXIT_OK
    render_runtime(cfg)
    return EXIT_OK if not cfg.env_keys_missing() else EXIT_WARN


def _dispatch_diff(args: argparse.Namespace) -> int:
    from .cmd_diff import build_diff_view, render_diff

    try:
        a = load_file_or_preset(args.source)
        b = load_file_or_preset(args.target)
    except FileNotFoundError as exc:
        print(f"dag-inspector: error: {exc}", file=sys.stderr)
        return EXIT_ERR
    if args.json:
        print(formatting.to_json(build_diff_view(a, b)))
        return EXIT_OK
    render_diff(a, b)
    return EXIT_OK


def _dispatch_validate(args: argparse.Namespace) -> int:
    from .cmd_validate import build_validation_view, render_validation

    if args.target == "active":
        cfg = load_active()
    else:
        try:
            cfg = load_file_or_preset(args.target)
        except FileNotFoundError as exc:
            print(f"dag-inspector: error: {exc}", file=sys.stderr)
            return EXIT_ERR
    view = build_validation_view(cfg)
    if args.json:
        print(formatting.to_json(view))
        # Use the highest severity as the exit code.
        sev = view.get("highest_severity", "ok")
        return {"ok": EXIT_OK, "info": EXIT_OK, "warning": EXIT_WARN, "error": EXIT_ERR}.get(
            sev, EXIT_OK
        )
    rc = render_validation(view)
    return rc


def _dispatch_coverage(args: argparse.Namespace) -> int:
    from .cmd_coverage import build_coverage_view, render_coverage

    if args.include_config == "active":
        cfg = load_active()
    else:
        try:
            cfg = load_file_or_preset(args.include_config)
        except FileNotFoundError as exc:
            print(f"dag-inspector: error: {exc}", file=sys.stderr)
            return EXIT_ERR
    view = build_coverage_view(cfg, lookback_min=args.lookback)
    if args.json:
        print(formatting.to_json(view))
        return EXIT_OK
    render_coverage(view)
    return EXIT_OK


def _dispatch_history(args: argparse.Namespace) -> int:
    from .cmd_history import build_history_view, render_history

    view = build_history_view(limit=args.limit)
    if args.json:
        print(formatting.to_json(view))
        return EXIT_OK
    render_history(view)
    return EXIT_OK