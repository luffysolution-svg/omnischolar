"""Configuration discovery, strict parsing, source tracking, and path resolution."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from platformdirs import user_config_path
from pydantic import ValidationError

from omnischolar.core.errors import OmniScholarError

from .models import OmniScholarConfig

_CONFIG_NAME = "omnischolar.config.json"


@dataclass(frozen=True, slots=True)
class ConfigSource:
    kind: Literal["explicit", "environment", "project", "user", "defaults"]
    path: Path | None
    base_directory: Path = field(default_factory=Path.cwd, repr=False)

    @property
    def directory(self) -> Path:
        return self.path.parent if self.path else self.base_directory

    def status(self) -> dict[str, str | None]:
        return {"kind": self.kind, "path": str(self.path) if self.path else None}


@dataclass(frozen=True, slots=True)
class LoadedConfig:
    config: OmniScholarConfig
    source: ConfigSource


def discover_config(
    explicit: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    user_directory: Path | None = None,
) -> ConfigSource:
    env = os.environ if environ is None else environ
    current = (cwd or Path.cwd()).resolve()
    candidates: list[tuple[str, Path]] = []
    if explicit is not None:
        candidates.append(("explicit", Path(explicit).expanduser()))
    elif env.get("OMNISCHOLAR_CONFIG"):
        candidates.append(("environment", Path(env["OMNISCHOLAR_CONFIG"]).expanduser()))
    else:
        candidates.extend(
            [
                ("project", current / _CONFIG_NAME),
                ("user", (user_directory or user_config_path("omnischolar")) / _CONFIG_NAME),
            ]
        )
    for kind, candidate in candidates:
        path = candidate if candidate.is_absolute() else current / candidate
        if path.is_file():
            if kind == "explicit":
                return ConfigSource("explicit", path.resolve(), current)
            if kind == "environment":
                return ConfigSource("environment", path.resolve(), current)
            if kind == "project":
                return ConfigSource("project", path.resolve(), current)
            return ConfigSource("user", path.resolve(), current)
    if explicit is not None or env.get("OMNISCHOLAR_CONFIG"):
        requested = candidates[0][1]
        raise OmniScholarError(
            "config_not_found", f"Configuration file was not found: {requested}", category="config"
        )
    return ConfigSource(kind="defaults", path=None, base_directory=current)


def _resolve_path(base: Path, path: Path | None) -> Path | None:
    if path is None:
        return None
    expanded = path.expanduser()
    return expanded.resolve() if expanded.is_absolute() else (base / expanded).resolve()


def _resolve_paths(config: OmniScholarConfig, base: Path) -> OmniScholarConfig:
    runtime = config.runtime.model_copy(
        update={
            "cache_directory": _resolve_path(base, config.runtime.cache_directory),
            "workspace_roots": [
                _resolve_path(base, item) for item in config.runtime.workspace_roots
            ],
        }
    )
    mineru = config.mineru.model_copy(
        update={"cache_directory": _resolve_path(base, config.mineru.cache_directory)}
    )
    materials = config.data.materials_project
    cas = config.data.cas_common_chemistry.model_copy(
        update={
            "contract_file": _resolve_path(base, config.data.cas_common_chemistry.contract_file)
        }
    )
    data = config.data.model_copy(
        update={"materials_project": materials, "cas_common_chemistry": cas}
    )
    providers = {
        name: provider.model_copy(
            update={"credentials_file": _resolve_path(base, provider.credentials_file)}
        )
        for name, provider in config.media.providers.items()
    }
    media = config.media.model_copy(update={"providers": providers})
    sync = config.sync.model_copy(
        update={"cache_directory": _resolve_path(base, config.sync.cache_directory)}
    )
    output = config.output.model_copy(
        update={"root_directory": _resolve_path(base, config.output.root_directory)}
    )
    return config.model_copy(
        update={
            "runtime": runtime,
            "mineru": mineru,
            "data": data,
            "media": media,
            "sync": sync,
            "output": output,
        }
    )


def load_config(
    path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    user_directory: Path | None = None,
) -> LoadedConfig:
    source = discover_config(path, environ=environ, cwd=cwd, user_directory=user_directory)
    payload: dict[str, Any] = {}
    if source.path:
        try:
            raw = source.path.read_bytes()
            if len(raw) > 4 * 1024 * 1024:
                raise OmniScholarError(
                    "config_too_large", "Configuration exceeds 4 MiB", category="config"
                )
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise OmniScholarError(
                    "invalid_config", "Configuration root must be an object", category="config"
                )
            payload = value
        except json.JSONDecodeError as exc:
            raise OmniScholarError(
                "invalid_config_json",
                "Configuration is not valid JSON",
                category="config",
                cause=exc,
            ) from exc
        except OSError as exc:
            raise OmniScholarError(
                "config_read_failed",
                "Configuration could not be read",
                category="config",
                cause=exc,
            ) from exc
    try:
        config = OmniScholarConfig.model_validate(payload)
    except ValidationError as exc:
        issues = [
            {
                "location": ".".join(str(item) for item in error["loc"]),
                "type": error["type"],
                "message": error["msg"],
            }
            for error in exc.errors(include_input=False, include_url=False)
        ]
        raise OmniScholarError(
            "invalid_config",
            "Configuration validation failed",
            category="config",
            details={"issues": issues},
        ) from exc
    return LoadedConfig(_resolve_paths(config, source.directory), source)


def config_json_schema() -> dict[str, Any]:
    return OmniScholarConfig.model_json_schema(by_alias=True)
