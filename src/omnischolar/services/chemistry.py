"""CAS Common Chemistry integration that fails closed without a provider contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from omnischolar.core import OmniScholarError

from .transport import ServiceTransport


class ChemistryService:
    def __init__(
        self,
        transport: ServiceTransport,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        contract_file: Path | None = None,
    ) -> None:
        self.transport = transport
        self.api_key = api_key
        self.base_url = base_url
        self.contract_file = contract_file
        self._contract = self._load_contract(contract_file)

    @staticmethod
    def _load_contract(path: Path | None) -> dict[str, Any] | None:
        if path is None:
            return None
        try:
            value = json.loads(path.read_bytes())
        except (OSError, json.JSONDecodeError) as exc:
            raise OmniScholarError(
                "cas_contract_invalid",
                "CAS provider contract file is invalid",
                category="config",
                cause=exc,
            ) from exc
        if not isinstance(value, dict) or value.get("schemaVersion") != 1:
            raise OmniScholarError(
                "cas_contract_invalid",
                "CAS provider contract schema is unsupported",
                category="config",
            )
        return value

    def sources(self) -> dict[str, Any]:
        return {
            "id": "cas-common-chemistry",
            "enabled": bool(self._contract and self.base_url),
            "implementationStatus": "implemented"
            if self._contract and self.base_url
            else "contract_blocked",
            "credentialStatus": "configured" if self.api_key else "missing",
            "validationStatus": "live_untested",
            "docs": ["https://www.cas.org/services/commonchemistry-api"],
            "license": "CAS Common Chemistry public content: CC BY-NC 4.0",
            "limitations": [
                "CAS publishes access-request information but no public endpoint/schema contract; OmniScholar does not guess one."
            ],
        }

    def _blocked(self) -> None:
        if not self._contract or not self.base_url:
            raise OmniScholarError(
                "provider_contract_blocked",
                "CAS Common Chemistry requires provider-issued API contract material",
                category="capability",
            )
        if not self.api_key:
            raise OmniScholarError(
                "credential_required", "CAS credential is not configured", category="authentication"
            )

    async def search(self, query: str, *, limit: int = 20) -> Any:
        self._blocked()
        assert self._contract is not None and self.base_url is not None
        operation = self._contract.get("search")
        if not isinstance(operation, dict) or not operation.get("path"):
            raise OmniScholarError(
                "provider_contract_blocked",
                "CAS contract does not define search",
                category="capability",
            )
        return await self.transport.json(
            operation.get("method", "GET"),
            f"{self.base_url.rstrip('/')}/{str(operation['path']).lstrip('/')}",
            params={
                operation.get("queryParameter", "q"): query,
                operation.get("limitParameter", "limit"): min(limit, 100),
            },
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    async def get(self, identifier: str) -> Any:
        self._blocked()
        assert self._contract is not None and self.base_url is not None
        operation = self._contract.get("get")
        if not isinstance(operation, dict) or "{id}" not in str(operation.get("path")):
            raise OmniScholarError(
                "provider_contract_blocked",
                "CAS contract does not define identifier lookup",
                category="capability",
            )
        path = str(operation["path"]).replace("{id}", identifier)
        return await self.transport.json(
            operation.get("method", "GET"),
            f"{self.base_url.rstrip('/')}/{path.lstrip('/')}",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
