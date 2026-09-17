"""Local management CLI for WorkBuddy Delegate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

from workbuddy_bridge import (
    BridgeError,
    DEFAULT_CONFIG,
    config_path,
    delegate,
    load_config,
    prune_results,
    save_config,
    status,
    usage,
)


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Manage WorkBuddy Delegate. No command reads or prints API keys.")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check Python, Node, WorkBuddy, paths, and limits without a model call.")
    commands.add_parser("status", help="Alias of doctor.")
    commands.add_parser("self-test", help="Run an offline routing and safety smoke test.")

    config = commands.add_parser("config", help="Manage non-secret configuration.")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("path")
    config_commands.add_parser("show")
    config_commands.add_parser("init")
    setting = config_commands.add_parser("set")
    setting.add_argument("key", choices=sorted(set(DEFAULT_CONFIG) - {"allowed_roots"}))
    setting.add_argument("value")

    roots = commands.add_parser("roots", help="Manage directories from which explicit files may be delegated.")
    root_commands = roots.add_subparsers(dest="roots_command", required=True)
    root_commands.add_parser("list")
    add = root_commands.add_parser("add")
    add.add_argument("path")
    remove = root_commands.add_parser("remove")
    remove.add_argument("path")

    usage_parser = commands.add_parser("usage", help="Show local invocation counts, not monetary cost.")
    usage_parser.add_argument("--days", type=int, default=7)

    cache = commands.add_parser("cache", help="Manage locally stored result artifacts.")
    cache_commands = cache.add_subparsers(dest="cache_command", required=True)
    prune = cache_commands.add_parser("prune")
    prune.add_argument("--older-than-days", type=int)

    run = commands.add_parser("delegate", help="Run a JSON job; use --dry-run to avoid a model request.")
    run.add_argument("--job", required=True)
    run.add_argument("--dry-run", action="store_true")
    return root


def _coerce(key: str, value: str):
    if key in {"daily_call_limit", "max_input_chars", "timeout_seconds", "cache_hours", "retention_days"}:
        try:
            return int(value)
        except ValueError as exc:
            raise BridgeError(f"{key} requires an integer") from exc
    return value


def _roots(command: str, raw_path: str | None = None):
    cfg = load_config()
    values = list(cfg["allowed_roots"])
    if command == "list":
        return {"allowed_roots": values}
    path = Path(raw_path or "").expanduser().resolve(strict=True)
    if not path.is_dir():
        raise BridgeError("Allowed root must be an existing directory")
    normalized = str(path)
    if command == "add" and normalized not in values:
        values.append(normalized)
    if command == "remove":
        values = [item for item in values if str(Path(item).expanduser().resolve()) != normalized]
    saved = save_config({"allowed_roots": values})
    return {"allowed_roots": saved["allowed_roots"]}


def _self_test():
    with tempfile.TemporaryDirectory() as temporary:
        result = delegate(
            instruction="Rewrite the provided text in plain language.",
            workspace=temporary,
            kind="rewrite",
            risk="low",
            text="A short offline fixture.",
            dry_run=True,
        )
    if result.get("request_sent") is not False or result.get("route") != "workbuddy":
        raise BridgeError("Offline routing self-test failed")
    return {"status": "passed", "model_request_sent": False, "checks": ["config", "routing", "dry_run"]}


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command in {"doctor", "status"}:
            value = status()
        elif args.command == "self-test":
            value = _self_test()
        elif args.command == "usage":
            value = usage(args.days)
        elif args.command == "cache":
            value = prune_results(args.older_than_days)
        elif args.command == "roots":
            value = _roots(args.roots_command, getattr(args, "path", None))
        elif args.command == "delegate":
            job_path = Path(args.job).expanduser().resolve(strict=True)
            job = json.loads(job_path.read_text(encoding="utf-8-sig"))
            if not isinstance(job, dict):
                raise BridgeError("Job file must contain a JSON object")
            value = delegate(**job, dry_run=args.dry_run)
        elif args.config_command == "path":
            value = {"config_path": str(config_path())}
        elif args.config_command == "show":
            value = load_config()
        elif args.config_command == "init":
            value = save_config({})
        else:
            value = save_config({args.key: _coerce(args.key, args.value)})
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0
    except (BridgeError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
