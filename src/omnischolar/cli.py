"""OmniScholar command-line interface."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from omnischolar.config import config_json_schema, load_config
from omnischolar.core import OmniScholarError, atomic_write, redact
from omnischolar.hosts.installer import (
    HOSTS,
    manage_host,
    manage_mcp,
    manage_skills,
    official_npx_commands,
    rollback,
)
from omnischolar.mcp.server import run_stdio
from omnischolar.runtime import OmniScholarRuntime
from omnischolar.version import __version__


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omnischolar", description="Literature, Zotero, PDF, citation, materials, and image tools"
    )
    parser.add_argument("--version", action="version", version=f"omnischolar {__version__}")
    parser.add_argument("--config", type=Path, help="Explicit omnischolar.config.json path")
    commands = parser.add_subparsers(dest="command")
    mcp = commands.add_parser("mcp", help="Run MCP or manage a host MCP configuration")
    mcp.add_argument("mcp_action", nargs="?", choices=("install", "status", "uninstall"))
    mcp.add_argument("mcp_host", nargs="?", choices=HOSTS)
    mcp.add_argument("--scope", choices=("user", "project"), default="user")
    mcp.add_argument("--project-dir", type=Path)
    mcp.add_argument("--dry-run", action="store_true")

    for operation in ("install", "update", "uninstall"):
        command = commands.add_parser(operation, help=f"{operation.title()} host MCP and Skills")
        command.add_argument("target", choices=(*HOSTS, "skills"))
        command.add_argument("host", nargs="?", choices=HOSTS)
        command.add_argument("--scope", choices=("user", "project"), default="user")
        command.add_argument("--project-dir", type=Path)
        command.add_argument("--dry-run", action="store_true")
    rollback_command = commands.add_parser(
        "rollback", help="Restore an OmniScholar host-config or Skills backup"
    )
    rollback_command.add_argument("backup", type=Path)
    npx = commands.add_parser("npx-skills", help="Show verified official npx Skills commands")
    npx.add_argument("host", choices=HOSTS)
    commands.add_parser("status", help="Show configured services without printing API keys")
    doctor = commands.add_parser(
        "doctor", help="Check configuration, tools, output access, and service credentials"
    )
    doctor.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    config = commands.add_parser("config", help="Inspect configuration")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("path", help="Print selected configuration path")
    config_commands.add_parser("schema", help="Print schemaVersion 1 JSON Schema")
    return parser


def _print(value: Any) -> None:
    sys.stdout.write(json.dumps(redact(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n")


async def _status(config_path: Path | None) -> int:
    loaded = load_config(config_path)
    async with OmniScholarRuntime(loaded) as runtime:
        _print(await runtime.application.status())
    return 0


async def _doctor(config_path: Path | None, as_json: bool) -> int:
    loaded = load_config(config_path)
    checks: list[dict[str, Any]] = [
        {"name": "config", "status": "success", "source": loaded.source.status()}
    ]
    async with OmniScholarRuntime(loaded) as runtime:
        registry = runtime.require_registry()
        checks.append(
            {
                "name": "tool-registry",
                "status": "success",
                "tools": len(registry.list()),
                "allTools": len(registry.list(enabled_only=False)),
            }
        )
        output = loaded.config.output.root_directory
        try:
            marker = f".omnischolar/doctor-{os.getpid()}"
            await atomic_write(output, marker, b"ok")
            (output / marker).unlink(missing_ok=True)
            checks.append({"name": "output-safe-write", "status": "success", "path": str(output)})
        except (OSError, OmniScholarError) as error:
            checks.append({"name": "output-safe-write", "status": "failed", "error": str(error)})
        status = await runtime.application.status()
        checks.append(
            {"name": "providers", "status": "success", "credentials": status["credentials"]}
        )
        checks.append(
            {"name": "zotero", "status": "not_checked", "reason": "doctor is offline by default"}
        )
    success = all(check["status"] not in {"failed"} for check in checks)
    result = {"success": success, "checks": checks}
    if as_json:
        _print(result)
    else:
        for check in checks:
            sys.stdout.write(f"{check['name']}: {check['status']}\n")
    return 0 if success else 1


async def _run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "mcp":
        if args.mcp_action is not None:
            if args.mcp_host is None:
                parser.error("omnischolar mcp install/status/uninstall requires a host")
            environment = None
            if args.project_dir is not None:
                from omnischolar.hosts.installer import InstallEnvironment

                environment = InstallEnvironment.current(args.project_dir)
            result = await manage_mcp(
                args.mcp_host,
                args.mcp_action,
                scope=args.scope,
                dry_run=args.dry_run,
                environment=environment,
                handshake=args.mcp_action != "status",
            )
            _print(result.json())
            return 0
        if args.mcp_host is not None:
            parser.error("MCP host requires install/status/uninstall")
        await run_stdio(args.config)
        return 0
    if args.command in {"install", "update", "uninstall"}:
        operation = args.command
        selected_host = args.host if args.target == "skills" else args.target
        if args.target == "skills" and selected_host is None:
            parser.error(f"omnischolar {operation} skills requires a host")
        if args.target != "skills" and args.host is not None:
            parser.error("Unexpected second host argument")
        assert selected_host is not None
        environment = None
        if args.project_dir is not None:
            from omnischolar.hosts.installer import InstallEnvironment

            environment = InstallEnvironment.current(args.project_dir)
        if args.target == "skills":
            value = manage_skills(
                selected_host,
                operation,
                scope=args.scope,
                dry_run=args.dry_run,
                environment=environment,
            )
            _print(value.json())
        else:
            values = await manage_host(
                selected_host,
                operation,
                scope=args.scope,
                dry_run=args.dry_run,
                environment=environment,
            )
            _print([value.json() for value in values])
        return 0
    if args.command == "rollback":
        _print({"status": "restored", "path": str(rollback(args.backup))})
        return 0
    if args.command == "npx-skills":
        _print(official_npx_commands(args.host))
        return 0
    if args.command == "status":
        return await _status(args.config)
    if args.command == "doctor":
        return await _doctor(args.config, args.json)
    if args.command == "config" and args.config_command == "path":
        loaded = load_config(args.config)
        sys.stdout.write((str(loaded.source.path) if loaded.source.path else "defaults") + "\n")
        return 0
    if args.command == "config" and args.config_command == "schema":
        _print(config_json_schema())
        return 0
    parser.error("Unknown command")
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_run(args, parser))
    except OmniScholarError as error:
        sys.stderr.write(json.dumps(redact(error.to_dict()), ensure_ascii=False) + "\n")
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
