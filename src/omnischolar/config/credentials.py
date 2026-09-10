"""Credential resolution with one precedence rule for all providers."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from pydantic import SecretStr

from omnischolar.core.errors import OmniScholarError

_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

STANDARD_ENVIRONMENTS: dict[str, tuple[str, ...]] = {
    "semantic-scholar": (
        "OMNISCHOLAR_SEMANTIC_SCHOLAR_API_KEY",
        "S2_API_KEY",
        "SEMANTIC_SCHOLAR_API_KEY",
    ),
    "unpaywall": ("OMNISCHOLAR_UNPAYWALL_API_KEY",),
    "easyscholar": ("OMNISCHOLAR_EASYSCHOLAR_API_KEY", "EASYSCHOLAR_API_KEY"),
    "ai4scholar": ("OMNISCHOLAR_AI4SCHOLAR_API_KEY", "AI4SCHOLAR_API_KEY"),
    "mineru": (
        "OMNISCHOLAR_MINERU_API_KEY",
        "MINERU_API_TOKEN",
        "MINERU_API_KEY",
    ),
    "materials-project": ("OMNISCHOLAR_MATERIALS_PROJECT_API_KEY", "MP_API_KEY"),
    "cas": ("OMNISCHOLAR_CAS_API_KEY", "CAS_API_KEY"),
    "openai": ("OMNISCHOLAR_OPENAI_API_KEY", "OPENAI_API_KEY"),
    "xai": ("OMNISCHOLAR_XAI_API_KEY", "XAI_API_KEY"),
    "fal": ("OMNISCHOLAR_FAL_API_KEY", "FAL_KEY"),
    "dashscope": ("OMNISCHOLAR_DASHSCOPE_API_KEY", "DASHSCOPE_API_KEY"),
    "qwen": ("OMNISCHOLAR_QWEN_API_KEY", "DASHSCOPE_API_KEY"),
    "gemini": ("OMNISCHOLAR_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "atlas": ("OMNISCHOLAR_ATLAS_API_KEY", "ATLAS_API_KEY"),
}


def validate_env_name(name: str) -> str:
    if not _ENV_NAME.fullmatch(name):
        raise OmniScholarError(
            "invalid_env_name",
            "apiKeyEnv is not a valid environment variable name",
            category="config",
        )
    return name


@dataclass(frozen=True, slots=True)
class ResolvedCredential:
    service: str
    source: str | None
    _value: str | None = field(default=None, repr=False)

    @property
    def configured(self) -> bool:
        return self._value is not None

    def reveal(self) -> str | None:
        return self._value

    def status(self) -> dict[str, str | bool | None]:
        return {"configured": self.configured, "source": self.source}


def resolve_credential(
    service: str,
    *,
    api_key: SecretStr | str | None = None,
    api_key_env: str | None = None,
    standard_env: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> ResolvedCredential:
    env = os.environ if environ is None else environ
    inline = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
    if inline and inline.strip():
        return ResolvedCredential(service, "config.apiKey", inline.strip())
    if api_key_env:
        name = validate_env_name(api_key_env)
        value = env.get(name, "").strip()
        if value:
            return ResolvedCredential(service, f"env:{name}", value)
    names = tuple(standard_env or STANDARD_ENVIRONMENTS.get(service, ()))
    for name in names:
        validate_env_name(name)
        value = env.get(name, "").strip()
        if value:
            return ResolvedCredential(service, f"env:{name}", value)
    return ResolvedCredential(service, None, None)
