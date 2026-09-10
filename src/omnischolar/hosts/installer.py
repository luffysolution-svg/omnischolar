"""Transactional host MCP and Agent Skills installer."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator, Mapping, MutableMapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, TextIO
from uuid import uuid4

import tomlkit
import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from omnischolar.core import OmniScholarError
from omnischolar.version import __version__

HostId = Literal["codex", "claude", "cursor", "opencode", "workbuddy", "hermes", "pi"]
Scope = Literal["user", "project"]
Operation = Literal["install", "update", "uninstall", "status"]
ConfigFormat = Literal["json", "jsonc", "yaml", "toml"]
InstallStatus = Literal[
    "installed",
    "updated",
    "removed",
    "already_installed",
    "not_installed",
    "planned",
    "manual_required",
]
HOSTS: tuple[HostId, ...] = (
    "codex",
    "claude",
    "cursor",
    "opencode",
    "workbuddy",
    "hermes",
    "pi",
)


@dataclass(frozen=True, slots=True)
class HostContract:
    id: HostId
    config_format: ConfigFormat | None
    user_config: str | None
    project_config: str | None
    server_key: str | None
    server_value: Mapping[str, Any] | None
    user_skills: str | None
    project_skills: str | None
    skills_agent: str | None
    manual_reason: str | None = None


CONTRACTS: dict[HostId, HostContract] = {
    "codex": HostContract(
        "codex",
        "toml",
        ".codex/config.toml",
        ".codex/config.toml",
        "mcp_servers",
        {"command": "omnischolar", "args": ["mcp"]},
        ".codex/skills",
        ".agents/skills",
        "codex",
    ),
    "claude": HostContract(
        "claude",
        "json",
        ".claude.json",
        ".mcp.json",
        "mcpServers",
        {"type": "stdio", "command": "omnischolar", "args": ["mcp"]},
        ".claude/skills",
        ".claude/skills",
        "claude-code",
    ),
    "cursor": HostContract(
        "cursor",
        "json",
        ".cursor/mcp.json",
        ".cursor/mcp.json",
        "mcpServers",
        {"type": "stdio", "command": "omnischolar", "args": ["mcp"]},
        ".cursor/skills",
        ".agents/skills",
        "cursor",
    ),
    "opencode": HostContract(
        "opencode",
        "jsonc",
        ".config/opencode/opencode.json",
        "opencode.jsonc",
        "mcp",
        {
            "type": "local",
            "command": ["omnischolar", "mcp"],
            "enabled": True,
            "timeout": 10000,
        },
        ".config/opencode/skills",
        ".agents/skills",
        "opencode",
    ),
    "workbuddy": HostContract(
        "workbuddy",
        "json",
        ".codebuddy/.mcp.json",
        ".mcp.json",
        "mcpServers",
        {
            "type": "stdio",
            "command": "omnischolar",
            "args": ["mcp"],
            "description": "OmniScholar research tools",
        },
        None,
        None,
        None,
        "WorkBuddy/CodeBuddy does not document a portable Skills installation path.",
    ),
    "hermes": HostContract(
        "hermes",
        "yaml",
        ".hermes/config.yaml",
        None,
        "mcp_servers",
        {"command": "omnischolar", "args": ["mcp"]},
        ".hermes/skills",
        ".hermes/skills",
        "hermes-agent",
        "Hermes documents MCP configuration only in the user-level ~/.hermes/config.yaml file.",
    ),
    "pi": HostContract(
        "pi",
        None,
        None,
        None,
        None,
        None,
        ".pi/agent/skills",
        ".pi/skills",
        "pi",
        "Pi connects through the @luffysolution/omnischolar-pi Extension installed by the full host installer.",
    ),
}

PI_EXTENSION_PACKAGE = "@luffysolution/omnischolar-pi"
PI_EXTENSION_SOURCE = f"npm:{PI_EXTENSION_PACKAGE}"


@dataclass(frozen=True, slots=True)
class InstallEnvironment:
    home: Path
    project: Path
    platform: str = sys.platform

    @classmethod
    def current(cls, project: Path | None = None) -> InstallEnvironment:
        return cls(Path.home().resolve(), (project or Path.cwd()).resolve(), sys.platform)


@dataclass(frozen=True, slots=True)
class InstallResult:
    component: Literal["mcp", "skills", "extension"]
    host: HostId
    operation: Operation
    scope: Scope
    status: InstallStatus
    path: str | None
    backup: str | None = None
    handshake: bool | None = None
    detail: str | None = None

    def json(self) -> dict[str, Any]:
        return asdict(self)


def _contract(host: str) -> HostContract:
    if host not in CONTRACTS:
        raise OmniScholarError("unknown_host", f"Unknown host: {host}", category="validation")
    return CONTRACTS[host]


def _target(base: Path, relative: str) -> Path:
    target = (base / relative).resolve()
    try:
        target.relative_to(base.resolve())
    except ValueError as exc:
        raise OmniScholarError(
            "unsafe_install_path", "Install path escapes its selected scope", category="filesystem"
        ) from exc
    return target


def config_path(
    contract: HostContract, scope: Scope, environment: InstallEnvironment
) -> Path | None:
    relative = contract.user_config if scope == "user" else contract.project_config
    if relative is None:
        return None
    base = environment.home if scope == "user" else environment.project
    return _target(base, relative)


def skills_path(
    contract: HostContract, scope: Scope, environment: InstallEnvironment
) -> Path | None:
    relative = contract.user_skills if scope == "user" else contract.project_skills
    if relative is None:
        return None
    base = environment.home if scope == "user" else environment.project
    return _target(base, relative)


def _strip_json_comments(text: str) -> str:
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == "/" and next_char == "/":
            index += 2
            while index < len(text) and text[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < len(text) and text[index : index + 2] != "*/":
                index += 1
            if index + 1 >= len(text):
                raise OmniScholarError(
                    "invalid_host_config", "JSONC block comment is unterminated", category="config"
                )
            index += 2
            continue
        output.append(char)
        index += 1
    return "".join(output)


def _load_document(path: Path, format_name: ConfigFormat) -> Any:
    if not path.exists():
        return tomlkit.document() if format_name == "toml" else {}
    if path.is_symlink() or not path.is_file():
        raise OmniScholarError(
            "unsafe_install_path",
            "Host configuration must be a regular file",
            category="filesystem",
        )
    try:
        text = path.read_text(encoding="utf-8")
        if format_name == "toml":
            return tomlkit.parse(text)
        if format_name == "yaml":
            value = yaml.safe_load(text)
        else:
            value = json.loads(_strip_json_comments(text) if format_name == "jsonc" else text)
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        raise OmniScholarError(
            "invalid_host_config",
            "Host configuration could not be parsed",
            category="config",
            cause=exc,
        ) from exc
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise OmniScholarError(
            "invalid_host_config", "Host configuration root must be an object", category="config"
        )
    return value


def _serialize_document(value: Any, format_name: ConfigFormat) -> bytes:
    if format_name == "toml":
        return tomlkit.dumps(value).encode("utf-8")
    if format_name == "yaml":
        serialized = yaml.safe_dump(value, sort_keys=False, allow_unicode=True)
        if not isinstance(serialized, str):
            raise OmniScholarError(
                "invalid_host_config", "YAML serializer did not return text", category="config"
            )
        return serialized.encode("utf-8")
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or (path.exists() and path.is_symlink()):
        raise OmniScholarError(
            "unsafe_install_path",
            "Refusing to write through a symbolic link",
            category="filesystem",
        )
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.omnischolar-backup-{time.time_ns()}-{uuid4().hex[:8]}")
    shutil.copy2(path, backup)
    return backup


def _server_table(document: Any, key: str, *, create: bool) -> MutableMapping[str, Any] | None:
    existing = document.get(key)
    if existing is None and create:
        document[key] = tomlkit.table() if hasattr(document, "as_string") else {}
        existing = document[key]
    if existing is not None and not isinstance(existing, MutableMapping):
        raise OmniScholarError(
            "invalid_host_config", f"Host configuration {key} must be an object", category="config"
        )
    return existing


def _is_owned_server(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    command = value.get("command")
    args = value.get("args")
    return (command == "omnischolar" and list(args or []) == ["mcp"]) or command == [
        "omnischolar",
        "mcp",
    ]


def _restore_file(path: Path, backup: Path | None, existed: bool) -> None:
    if backup is not None and backup.exists():
        shutil.copy2(backup, path)
    elif not existed:
        path.unlink(missing_ok=True)


@contextmanager
def _stdio_error_sink() -> Iterator[TextIO]:
    with open(os.devnull, "w", encoding="utf-8") as errors:
        yield errors


async def verify_mcp_handshake(*, timeout_seconds: float = 20.0) -> dict[str, Any]:
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "omnischolar", "mcp"])
    try:
        with _stdio_error_sink() as errors:
            async with asyncio.timeout(timeout_seconds):
                async with stdio_client(parameters, errlog=errors) as streams:
                    async with ClientSession(*streams) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        status = await session.call_tool("omnischolar_status", {})
                        if status.isError:
                            raise OmniScholarError(
                                "mcp_handshake_failed",
                                "Installed MCP server returned an error for omnischolar_status",
                                category="host",
                            )
                        return {"tools": len(tools.tools), "status": "success"}
    except OmniScholarError:
        raise
    except TimeoutError as exc:
        raise OmniScholarError(
            "mcp_handshake_timeout",
            "Installed MCP server did not complete its handshake before the deadline",
            category="host",
            cause=exc,
        ) from exc
    except Exception as exc:
        raise OmniScholarError(
            "mcp_handshake_failed",
            "Installed MCP server could not complete its handshake",
            category="host",
            cause=exc,
        ) from exc


async def manage_mcp(
    host: str,
    operation: Operation,
    *,
    scope: Scope = "user",
    dry_run: bool = False,
    environment: InstallEnvironment | None = None,
    handshake: bool = True,
) -> InstallResult:
    contract = _contract(host)
    env = environment or InstallEnvironment.current()
    path = config_path(contract, scope, env)
    if path is None or contract.config_format is None or contract.server_key is None:
        return InstallResult(
            "mcp",
            contract.id,
            operation,
            scope,
            "manual_required",
            None,
            detail=contract.manual_reason,
        )
    document = _load_document(path, contract.config_format)
    table = _server_table(document, contract.server_key, create=operation != "status")
    current = table.get("omnischolar") if isinstance(table, Mapping) else None
    if operation == "status":
        status: InstallStatus = (
            "already_installed" if _is_owned_server(current) else "not_installed"
        )
        return InstallResult("mcp", contract.id, operation, scope, status, str(path))
    if operation == "uninstall":
        if current is None:
            return InstallResult("mcp", contract.id, operation, scope, "not_installed", str(path))
        if not _is_owned_server(current):
            raise OmniScholarError(
                "installation_conflict",
                "The existing omnischolar MCP entry is not managed by OmniScholar",
                category="host",
            )
    else:
        if current == contract.server_value:
            existing_handshake_ok: bool | None = None
            if handshake:
                await verify_mcp_handshake()
                existing_handshake_ok = True
            return InstallResult(
                "mcp",
                contract.id,
                operation,
                scope,
                "already_installed",
                str(path),
                handshake=existing_handshake_ok,
            )
        if operation == "update" and current is None:
            return InstallResult("mcp", contract.id, operation, scope, "not_installed", str(path))
        if current is not None and not _is_owned_server(current):
            raise OmniScholarError(
                "installation_conflict",
                "An unrelated omnischolar MCP entry already exists",
                category="host",
            )
        if operation == "install" and current is not None:
            raise OmniScholarError(
                "installation_conflict",
                "Install does not overwrite an existing MCP entry; use update",
                category="host",
            )
    if dry_run:
        return InstallResult("mcp", contract.id, operation, scope, "planned", str(path))

    if table is None:
        raise OmniScholarError(
            "invalid_host_config",
            f"Host configuration {contract.server_key} is missing",
            category="config",
        )
    existed = path.exists()
    backup = _backup_file(path)
    if operation == "uninstall":
        del table["omnischolar"]
    else:
        table["omnischolar"] = dict(contract.server_value or {})
    try:
        _atomic_write(path, _serialize_document(document, contract.config_format))
        handshake_ok: bool | None = None
        if operation != "uninstall" and handshake:
            await verify_mcp_handshake()
            handshake_ok = True
    except BaseException:
        _restore_file(path, backup, existed)
        raise
    final_status: InstallStatus = (
        "removed"
        if operation == "uninstall"
        else ("updated" if current is not None else "installed")
    )
    return InstallResult(
        "mcp",
        contract.id,
        operation,
        scope,
        final_status,
        str(path),
        str(backup) if backup else None,
        handshake_ok,
    )


def bundled_skills_root() -> Path:
    source_tree = Path(__file__).resolve().parents[3] / "skills"
    if source_tree.is_dir():
        return source_tree
    from importlib.resources import files

    bundled = files("omnischolar").joinpath("share", "skills")
    path = Path(str(bundled))
    if not path.is_dir():
        raise OmniScholarError(
            "skills_not_bundled",
            "Installed distribution does not contain Skills",
            category="package",
        )
    return path


def _skill_checksums(root: Path) -> dict[str, str]:
    if root.is_symlink():
        raise OmniScholarError(
            "unsafe_install_path",
            "Skill directories cannot be symbolic links",
            category="filesystem",
        )
    values: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise OmniScholarError(
                "unsafe_install_path",
                "Skill content cannot contain symbolic links",
                category="filesystem",
            )
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            values[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return values


def _manifest_path(target: Path) -> Path:
    return target / ".omnischolar-install.json"


def _validated_skill_manifest(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schemaVersion") != 1:
        raise OmniScholarError(
            "invalid_install_manifest", "Skills install manifest schema is invalid", category="host"
        )
    skills = value.get("skills")
    checksums = value.get("checksums")
    if (
        not isinstance(skills, list)
        or not skills
        or not all(
            isinstance(name, str)
            and name
            and not name.startswith(".")
            and Path(name).name == name
            and "/" not in name
            and "\\" not in name
            for name in skills
        )
        or len(set(skills)) != len(skills)
        or not isinstance(checksums, dict)
    ):
        raise OmniScholarError(
            "invalid_install_manifest",
            "Skills install manifest entries are invalid",
            category="host",
        )
    skill_names = set(skills)
    for relative, digest in checksums.items():
        if (
            not isinstance(relative, str)
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or relative.split("/", 1)[0] not in skill_names
            or relative.startswith("/")
            or "\\" in relative
            or any(part in {"", ".", ".."} for part in relative.split("/"))
        ):
            raise OmniScholarError(
                "invalid_install_manifest",
                "Skills install manifest checksums are invalid",
                category="host",
            )
    if any(f"{name}/SKILL.md" not in checksums for name in skills):
        raise OmniScholarError(
            "invalid_install_manifest",
            "Skills install manifest is missing a SKILL.md checksum",
            category="host",
        )
    return value


def _manifest_skill_names(manifest: Mapping[str, Any]) -> list[str]:
    value = manifest.get("skills")
    if not isinstance(value, list) or not all(isinstance(name, str) for name in value):
        raise OmniScholarError(
            "invalid_install_manifest",
            "Skills install manifest entries are invalid",
            category="host",
        )
    return [name for name in value if isinstance(name, str)]


def _load_skill_manifest(target: Path) -> dict[str, Any] | None:
    path = _manifest_path(target)
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise OmniScholarError(
            "unsafe_install_path",
            "Skills install manifest must be a regular file",
            category="filesystem",
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OmniScholarError(
            "invalid_install_manifest",
            "Skills install manifest is invalid",
            category="host",
            cause=exc,
        ) from exc
    return _validated_skill_manifest(value)


def _installed_skills_match(target: Path, manifest: Mapping[str, Any]) -> bool:
    expected = manifest.get("checksums")
    if not isinstance(expected, dict):
        return False
    actual: dict[str, str] = {}
    for skill in _manifest_skill_names(manifest):
        directory = target / skill
        if not directory.is_dir():
            return False
        actual.update(
            {f"{skill}/{key}": value for key, value in _skill_checksums(directory).items()}
        )
    return actual == expected


def manage_skills(
    host: str,
    operation: Operation,
    *,
    scope: Scope = "user",
    dry_run: bool = False,
    environment: InstallEnvironment | None = None,
    source: Path | None = None,
) -> InstallResult:
    contract = _contract(host)
    env = environment or InstallEnvironment.current()
    target = skills_path(contract, scope, env)
    if target is None:
        return InstallResult(
            "skills",
            contract.id,
            operation,
            scope,
            "manual_required",
            None,
            detail=contract.manual_reason,
        )
    manifest = _load_skill_manifest(target)
    if operation == "status":
        is_installed = manifest is not None and _installed_skills_match(target, manifest)
        return InstallResult(
            "skills",
            contract.id,
            operation,
            scope,
            "already_installed" if is_installed else "not_installed",
            str(target),
        )
    if operation == "uninstall":
        if manifest is None:
            return InstallResult(
                "skills", contract.id, operation, scope, "not_installed", str(target)
            )
        if not _installed_skills_match(target, manifest):
            raise OmniScholarError(
                "skills_modified",
                "Installed Skills contain local modifications and were preserved",
                category="conflict",
            )
        if dry_run:
            return InstallResult("skills", contract.id, operation, scope, "planned", str(target))
        skill_names = _manifest_skill_names(manifest)
        uninstall_backup = target / ".omnischolar-backups" / f"{time.time_ns()}-{uuid4().hex[:8]}"
        uninstall_backup.mkdir(parents=True, exist_ok=False)
        for name in skill_names:
            shutil.copytree(target / name, uninstall_backup / name)
        shutil.copy2(_manifest_path(target), uninstall_backup / ".omnischolar-install.json")
        try:
            for name in skill_names:
                shutil.rmtree(target / name)
            _manifest_path(target).unlink()
        except BaseException:
            for name in skill_names:
                source_directory = uninstall_backup / name
                if source_directory.is_dir():
                    shutil.copytree(source_directory, target / name, dirs_exist_ok=True)
            shutil.copy2(uninstall_backup / ".omnischolar-install.json", _manifest_path(target))
            raise
        return InstallResult(
            "skills", contract.id, operation, scope, "removed", str(target), str(uninstall_backup)
        )

    if operation == "update" and manifest is None:
        return InstallResult("skills", contract.id, operation, scope, "not_installed", str(target))

    source_root = (source or bundled_skills_root()).resolve()
    skill_dirs = sorted(path for path in source_root.iterdir() if (path / "SKILL.md").is_file())
    if not skill_dirs:
        raise OmniScholarError(
            "skills_not_bundled", "No bundled Skills were found", category="package"
        )
    names = [path.name for path in skill_dirs]
    checksums: dict[str, str] = {}
    for directory in skill_dirs:
        checksums.update(
            {f"{directory.name}/{key}": value for key, value in _skill_checksums(directory).items()}
        )
    desired = {
        "schemaVersion": 1,
        "distribution": "luffysolution-omnischolar",
        "version": __version__,
        "skills": names,
        "checksums": checksums,
    }
    if manifest == desired and _installed_skills_match(target, desired):
        return InstallResult(
            "skills", contract.id, operation, scope, "already_installed", str(target)
        )
    for name in names:
        destination = target / name
        if destination.exists() and manifest is None:
            raise OmniScholarError(
                "installation_conflict",
                f"Skill directory {name} already exists and is not managed by OmniScholar",
                category="host",
            )
    if operation == "install" and manifest is not None:
        raise OmniScholarError(
            "installation_conflict",
            "Skills are already managed; use update",
            category="host",
        )
    if manifest is not None and not _installed_skills_match(target, manifest):
        raise OmniScholarError(
            "skills_modified",
            "Installed Skills contain local modifications and were preserved",
            category="conflict",
        )
    if dry_run:
        return InstallResult("skills", contract.id, operation, scope, "planned", str(target))

    target.mkdir(parents=True, exist_ok=True)
    update_backup: Path | None = None
    if manifest is not None:
        update_backup = target / ".omnischolar-backups" / f"{time.time_ns()}-{uuid4().hex[:8]}"
        update_backup.mkdir(parents=True, exist_ok=False)
        for name in _manifest_skill_names(manifest):
            shutil.copytree(target / name, update_backup / name)
        shutil.copy2(_manifest_path(target), update_backup / ".omnischolar-install.json")
    copied_destinations: list[Path] = []
    try:
        for source_dir in skill_dirs:
            destination = target / source_dir.name
            if destination.exists():
                shutil.rmtree(destination)
            copied_destinations.append(destination)
            shutil.copytree(source_dir, destination)
        _atomic_write(
            _manifest_path(target),
            (json.dumps(desired, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(),
        )
    except BaseException:
        for destination in copied_destinations:
            shutil.rmtree(destination, ignore_errors=True)
        if update_backup is not None and manifest is not None:
            for name in _manifest_skill_names(manifest):
                shutil.copytree(update_backup / name, target / name, dirs_exist_ok=True)
            shutil.copy2(update_backup / ".omnischolar-install.json", _manifest_path(target))
        raise
    return InstallResult(
        "skills",
        contract.id,
        operation,
        scope,
        "updated" if manifest is not None else "installed",
        str(target),
        str(update_backup) if update_backup else None,
    )


def _pi_settings_path(scope: Scope, environment: InstallEnvironment) -> Path:
    base = environment.home if scope == "user" else environment.project
    relative = ".pi/agent/settings.json" if scope == "user" else ".pi/settings.json"
    return _target(base, relative)


def _pi_source_matches(value: object) -> bool:
    if isinstance(value, Mapping):
        value = value.get("source")
    if not isinstance(value, str):
        return False
    if value == PI_EXTENSION_SOURCE:
        return True
    return value.startswith(f"{PI_EXTENSION_SOURCE}@")


def _pi_extension_configured(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_symlink() or not path.is_file():
        raise OmniScholarError(
            "unsafe_install_path", "Pi settings must be a regular file", category="filesystem"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OmniScholarError(
            "invalid_host_config", "Pi settings could not be parsed", category="config", cause=exc
        ) from exc
    packages = document.get("packages", []) if isinstance(document, Mapping) else []
    if not isinstance(packages, list):
        raise OmniScholarError(
            "invalid_host_config", "Pi settings packages must be an array", category="config"
        )
    return any(_pi_source_matches(value) for value in packages)


async def _run_pi_command(arguments: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("pi")
    if executable is None:
        raise OmniScholarError(
            "pi_not_found",
            "Pi is not installed or is not available on PATH",
            category="host",
        )
    result = await asyncio.to_thread(
        subprocess.run,
        [executable, *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-2000:]
        raise OmniScholarError(
            "pi_extension_command_failed",
            f"Pi package command failed: {detail or 'unknown error'}",
            category="host",
        )
    return result


async def manage_pi_extension(
    operation: Operation,
    *,
    scope: Scope = "user",
    dry_run: bool = False,
    environment: InstallEnvironment | None = None,
) -> InstallResult:
    env = environment or InstallEnvironment.current()
    path = _pi_settings_path(scope, env)
    configured = _pi_extension_configured(path)
    if operation == "status":
        return InstallResult(
            "extension",
            "pi",
            operation,
            scope,
            "already_installed" if configured else "not_installed",
            str(path),
            detail=PI_EXTENSION_SOURCE,
        )
    if operation == "install" and configured:
        return InstallResult(
            "extension", "pi", operation, scope, "already_installed", str(path)
        )
    if operation in {"update", "uninstall"} and not configured:
        return InstallResult("extension", "pi", operation, scope, "not_installed", str(path))
    if dry_run:
        return InstallResult(
            "extension", "pi", operation, scope, "planned", str(path), detail=PI_EXTENSION_SOURCE
        )

    if operation == "install":
        arguments = ["install", PI_EXTENSION_SOURCE]
    elif operation == "update":
        arguments = ["update", PI_EXTENSION_SOURCE]
    else:
        arguments = ["remove", PI_EXTENSION_SOURCE]
    if scope == "project" and operation in {"install", "uninstall"}:
        arguments.extend(["--local", "--approve"])
    elif scope == "project":
        arguments.append("--approve")
    await _run_pi_command(arguments, cwd=env.project)

    final_configured = _pi_extension_configured(path)
    expected = operation != "uninstall"
    if final_configured != expected:
        raise OmniScholarError(
            "pi_extension_verification_failed",
            "Pi package command completed but settings do not contain the expected Extension state",
            category="host",
        )
    return InstallResult(
        "extension",
        "pi",
        operation,
        scope,
        "removed" if operation == "uninstall" else ("updated" if configured else "installed"),
        str(path),
        detail=PI_EXTENSION_SOURCE,
    )


async def manage_host(
    host: str,
    operation: Operation,
    *,
    scope: Scope = "user",
    dry_run: bool = False,
    environment: InstallEnvironment | None = None,
    handshake: bool = True,
) -> list[InstallResult]:
    if host == "pi":
        extension_plan = await manage_pi_extension(
            operation, scope=scope, dry_run=True, environment=environment
        )
        skills_plan = manage_skills(
            host, operation, scope=scope, dry_run=True, environment=environment
        )
        if dry_run:
            return [extension_plan, skills_plan]

        if operation == "uninstall":
            skills_result = manage_skills(
                host, operation, scope=scope, environment=environment
            )
            try:
                extension_result = await manage_pi_extension(
                    operation, scope=scope, environment=environment
                )
            except BaseException:
                if skills_result.backup is not None:
                    rollback(Path(skills_result.backup))
                raise
            return [extension_result, skills_result]

        extension_result = await manage_pi_extension(
            operation, scope=scope, environment=environment
        )
        try:
            skills_result = manage_skills(
                host, operation, scope=scope, environment=environment
            )
        except BaseException:
            if extension_result.status == "installed":
                await manage_pi_extension("uninstall", scope=scope, environment=environment)
            raise
        return [extension_result, skills_result]

    mcp_plan = await manage_mcp(
        host,
        operation,
        scope=scope,
        dry_run=True,
        environment=environment,
        handshake=False,
    )
    skills_plan = manage_skills(host, operation, scope=scope, dry_run=True, environment=environment)
    if dry_run:
        return [mcp_plan, skills_plan]

    mcp_result = await manage_mcp(
        host,
        operation,
        scope=scope,
        environment=environment,
        handshake=handshake,
    )
    try:
        skills_result = manage_skills(host, operation, scope=scope, environment=environment)
    except BaseException:
        if mcp_result.backup is not None:
            rollback(Path(mcp_result.backup))
        elif mcp_result.status == "installed" and mcp_result.path is not None:
            Path(mcp_result.path).unlink(missing_ok=True)
        raise
    return [mcp_result, skills_result]


def _rollback_host_config(source: Path) -> Path:
    marker = ".omnischolar-backup-"
    if marker not in source.name or not source.is_file():
        raise OmniScholarError(
            "invalid_backup",
            "Backup must be an OmniScholar host-config backup file",
            category="validation",
        )
    target_name = source.name.split(marker, 1)[0]
    target = source.with_name(target_name)
    _atomic_write(target, source.read_bytes())
    return target


def _rollback_skills(source: Path) -> Path:
    if source.parent.name != ".omnischolar-backups" or not source.is_dir():
        raise OmniScholarError(
            "invalid_backup",
            "Skills backup must be an OmniScholar-managed backup directory",
            category="validation",
        )
    backup_manifest = _load_skill_manifest(source)
    if backup_manifest is None or not _installed_skills_match(source, backup_manifest):
        raise OmniScholarError(
            "invalid_backup", "Skills backup is incomplete or modified", category="validation"
        )
    target = source.parent.parent
    current_manifest = _load_skill_manifest(target)
    if current_manifest is not None and not _installed_skills_match(target, current_manifest):
        raise OmniScholarError(
            "skills_modified",
            "Installed Skills contain local modifications and were preserved",
            category="conflict",
        )
    current_names = _manifest_skill_names(current_manifest) if current_manifest is not None else []
    backup_names = _manifest_skill_names(backup_manifest)
    for name in backup_names:
        destination = target / name
        if destination.exists() and name not in current_names:
            raise OmniScholarError(
                "installation_conflict",
                f"Skill directory {name} exists and is not managed by OmniScholar",
                category="host",
            )

    recovery: Path | None = None
    if current_manifest is not None:
        recovery = target / ".omnischolar-backups" / f"{time.time_ns()}-{uuid4().hex[:8]}"
        recovery.mkdir(parents=True, exist_ok=False)
        for name in current_names:
            shutil.copytree(target / name, recovery / name)
        shutil.copy2(_manifest_path(target), _manifest_path(recovery))
    restored: list[Path] = []
    try:
        for name in current_names:
            shutil.rmtree(target / name)
        for name in backup_names:
            destination = target / name
            restored.append(destination)
            shutil.copytree(source / name, destination)
        _atomic_write(_manifest_path(target), _manifest_path(source).read_bytes())
    except BaseException:
        for destination in restored:
            shutil.rmtree(destination, ignore_errors=True)
        _manifest_path(target).unlink(missing_ok=True)
        if recovery is not None and current_manifest is not None:
            for name in current_names:
                shutil.copytree(recovery / name, target / name, dirs_exist_ok=True)
            shutil.copy2(_manifest_path(recovery), _manifest_path(target))
        raise
    return target


def rollback(backup: Path) -> Path:
    if backup.is_symlink():
        raise OmniScholarError(
            "invalid_backup", "Backup cannot be a symbolic link", category="validation"
        )
    source = backup.resolve(strict=True)
    if source.is_dir():
        return _rollback_skills(source)
    return _rollback_host_config(source)


def official_npx_commands(
    host: str, repository: str = "luffysolution-svg/omnischolar"
) -> dict[str, str]:
    contract = _contract(host)
    if contract.skills_agent is None:
        return {}
    agent = contract.skills_agent
    return {
        "installProject": f"npx skills add {repository} --skill '*' -a {agent} -y",
        "installUser": f"npx skills add {repository} --skill '*' -a {agent} -g -y",
        "updateProject": "npx skills update -p -y",
        "updateUser": "npx skills update -g -y",
        "uninstallProject": f"npx skills remove --skill '*' -a {agent} -y",
        "uninstallUser": f"npx skills remove --skill '*' -a {agent} -g -y",
    }
