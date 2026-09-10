"""Materials Project REST service and safe local exports."""

from __future__ import annotations

import csv
import io
import json
import math
import re
from pathlib import Path
from typing import Any, cast

from omnischolar.core import OmniScholarError, atomic_write

from .transport import ServiceTransport

MATERIAL_ROUTES = {
    "summary": "/materials/summary/",
    "thermo": "/materials/thermo/",
    "electronic_structure": "/materials/electronic_structure/",
    "dielectric": "/materials/dielectric/",
    "elasticity": "/materials/elasticity/",
    "piezoelectric": "/materials/piezoelectric/",
    "magnetism": "/materials/magnetism/",
    "xas": "/materials/xas/",
    "phonon": "/materials/phonon/",
    "surface_properties": "/materials/surface_properties/",
    "oxidation_states": "/materials/oxidation_states/",
    "robocrys": "/materials/robocrys/",
    "synthesis": "/materials/synthesis/",
}

_ELEMENT = re.compile(r"^[A-Z][a-z]?$", re.ASCII)

SUMMARY_FILTERS = {
    "material_ids",
    "formula",
    "chemsys",
    "elements",
    "exclude_elements",
    "crystal_system",
    "spacegroup_number",
    "energy_above_hull_min",
    "energy_above_hull_max",
    "band_gap_min",
    "band_gap_max",
    "density_min",
    "density_max",
    "is_stable",
    "is_metal",
    "theoretical",
    "deprecated",
}


def _finite_number(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise OmniScholarError(
            "cif_structure_invalid", f"CIF {label} must be numeric", category="validation"
        )
    number = float(value)
    if not math.isfinite(number):
        raise OmniScholarError(
            "cif_structure_invalid", f"CIF {label} must be finite", category="validation"
        )
    return number


def _structure_to_cif(record: dict[str, Any]) -> str:
    structure = record.get("structure")
    if not isinstance(structure, dict):
        raise OmniScholarError(
            "cif_unavailable",
            "CIF export requires one record with a structure or cif field",
            category="validation",
        )
    lattice = structure.get("lattice")
    sites = structure.get("sites")
    if not isinstance(lattice, dict) or not isinstance(sites, list) or not sites:
        raise OmniScholarError(
            "cif_structure_invalid",
            "CIF structure must contain lattice and sites",
            category="validation",
        )
    if len(sites) > 100_000:
        raise OmniScholarError(
            "cif_structure_too_large", "CIF structure has too many sites", category="limits"
        )
    parameters = {
        key: _finite_number(lattice.get(key), f"lattice.{key}")
        for key in ("a", "b", "c", "alpha", "beta", "gamma")
    }
    if any(parameters[key] <= 0 for key in ("a", "b", "c")) or any(
        not 0 < parameters[key] < 180 for key in ("alpha", "beta", "gamma")
    ):
        raise OmniScholarError(
            "cif_structure_invalid",
            "CIF lattice lengths or angles are outside valid bounds",
            category="validation",
        )
    material_id = re.sub(r"[^A-Za-z0-9_]+", "_", str(record.get("material_id", "material")))
    lines = [
        f"data_{material_id or 'material'}",
        "_audit_creation_method 'OmniScholar Materials Project structure export'",
        "_symmetry_space_group_name_H-M 'P 1'",
        "_symmetry_Int_Tables_number 1",
        f"_cell_length_a {parameters['a']:.10g}",
        f"_cell_length_b {parameters['b']:.10g}",
        f"_cell_length_c {parameters['c']:.10g}",
        f"_cell_angle_alpha {parameters['alpha']:.10g}",
        f"_cell_angle_beta {parameters['beta']:.10g}",
        f"_cell_angle_gamma {parameters['gamma']:.10g}",
        "loop_",
        "_atom_site_label",
        "_atom_site_type_symbol",
        "_atom_site_fract_x",
        "_atom_site_fract_y",
        "_atom_site_fract_z",
        "_atom_site_occupancy",
    ]
    counts: dict[str, int] = {}
    for site_index, site in enumerate(sites, 1):
        if not isinstance(site, dict):
            raise OmniScholarError(
                "cif_structure_invalid", "CIF site must be an object", category="validation"
            )
        coordinates = site.get("abc")
        species = site.get("species")
        if (
            not isinstance(coordinates, list)
            or len(coordinates) != 3
            or not isinstance(species, list)
            or not species
        ):
            raise OmniScholarError(
                "cif_structure_invalid",
                "CIF site must contain abc coordinates and species",
                category="validation",
            )
        xyz = [
            _finite_number(value, f"sites[{site_index}].abc[{axis}]")
            for axis, value in enumerate(coordinates)
        ]
        for component in species:
            if not isinstance(component, dict) or not isinstance(component.get("element"), str):
                raise OmniScholarError(
                    "cif_structure_invalid",
                    "CIF species must contain an element",
                    category="validation",
                )
            element = component["element"]
            if not _ELEMENT.fullmatch(element):
                raise OmniScholarError(
                    "cif_structure_invalid",
                    "CIF species contains an invalid element symbol",
                    category="validation",
                )
            occupancy = _finite_number(
                component.get("occu", 1), f"sites[{site_index}].species.occupancy"
            )
            if not 0 < occupancy <= 1:
                raise OmniScholarError(
                    "cif_structure_invalid",
                    "CIF species occupancy must be greater than zero and at most one",
                    category="validation",
                )
            counts[element] = counts.get(element, 0) + 1
            lines.append(
                f"{element}{counts[element]} {element} "
                f"{xyz[0]:.10g} {xyz[1]:.10g} {xyz[2]:.10g} {occupancy:.10g}"
            )
    return "\n".join(lines) + "\n"


class MaterialsProjectService:
    def __init__(
        self,
        transport: ServiceTransport,
        *,
        api_key: str,
        base_url: str = "https://api.materialsproject.org",
        max_pages: int = 10,
    ) -> None:
        if not api_key:
            raise OmniScholarError(
                "credential_required",
                "Materials Project API key is not configured",
                category="authentication",
            )
        self.transport = transport
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_pages = min(max(max_pages, 1), 100)

    @property
    def headers(self) -> dict[str, str]:
        return {"X-API-KEY": self.api_key, "Accept": "application/json"}

    def capabilities(self) -> dict[str, Any]:
        return {
            "provider": "materials-project",
            "implementation": "REST",
            "routes": sorted(MATERIAL_ROUTES),
            "derived": {
                "phaseDiagram": "Returns one consistent formation_energy_per_atom dataset; local hull construction is not silently mixed with energy_above_hull.",
                "xrd": "Use an explicit route or installed pymatgen bridge; no guessed server endpoint.",
            },
            "docs": "https://api.materialsproject.org/docs",
            "credentialConfigured": True,
        }

    @staticmethod
    def _payload(value: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not isinstance(value, dict) or not isinstance(value.get("data"), list):
            raise OmniScholarError(
                "materials_schema_mismatch",
                "Materials Project response omitted data",
                category="provider",
            )
        records = [cast(dict[str, Any], item) for item in value["data"] if isinstance(item, dict)]
        raw_meta = value.get("meta")
        meta = cast(dict[str, Any], raw_meta) if isinstance(raw_meta, dict) else {}
        return records, meta

    async def search(
        self,
        filters: dict[str, Any],
        *,
        fields: list[str] | None = None,
        limit: int = 20,
        page: int = 1,
    ) -> dict[str, Any]:
        unknown = sorted(set(filters) - SUMMARY_FILTERS)
        if unknown:
            raise OmniScholarError(
                "unsupported_filter",
                f"Unsupported Materials filters: {', '.join(unknown)}",
                category="validation",
            )
        page = min(max(page, 1), self.max_pages)
        size = min(max(limit, 1), 1_000)
        params = {**filters, "_limit": size, "_skip": (page - 1) * size}
        if fields:
            params["_fields"] = ",".join(fields)
        records, meta = self._payload(
            await self.transport.json(
                "GET", f"{self.base_url}/materials/summary/", params=params, headers=self.headers
            )
        )
        return self._result("summary", records, fields, meta, page, size)

    async def route_search(
        self,
        route: str,
        filters: dict[str, Any],
        *,
        fields: list[str] | None = None,
        limit: int = 20,
        page: int = 1,
    ) -> dict[str, Any]:
        if route not in MATERIAL_ROUTES:
            raise OmniScholarError(
                "unsupported_route",
                f"Unknown Materials Project route: {route}",
                category="validation",
            )
        page = min(max(page, 1), self.max_pages)
        size = min(max(limit, 1), 1_000)
        params = {**filters, "_limit": size, "_skip": (page - 1) * size}
        if fields:
            params["_fields"] = ",".join(fields)
        records, meta = self._payload(
            await self.transport.json(
                "GET",
                f"{self.base_url}{MATERIAL_ROUTES[route]}",
                params=params,
                headers=self.headers,
            )
        )
        return self._result(route, records, fields, meta, page, size)

    async def get(
        self, material_id: str, *, fields: list[str] | None = None, route: str = "summary"
    ) -> dict[str, Any]:
        result = await self.route_search(
            route, {"material_ids": material_id}, fields=fields, limit=1
        )
        if not result["records"]:
            raise OmniScholarError(
                "not_found", f"Material {material_id} was not found", category="provider"
            )
        return {
            "provider": "materials-project",
            "route": route,
            "record": result["records"][0],
            "fieldStatus": result["fieldStatus"],
        }

    async def advanced(self, action: str, args: dict[str, Any]) -> dict[str, Any]:
        if action == "phase_diagram":
            chemsys = args.get("chemsys")
            if not chemsys:
                raise OmniScholarError(
                    "missing_chemsys", "phase_diagram requires chemsys", category="validation"
                )
            result = await self.route_search(
                "thermo",
                {"chemsys": chemsys},
                fields=[
                    "material_id",
                    "formula_pretty",
                    "composition",
                    "formation_energy_per_atom",
                ],
                limit=min(args.get("limit", 500), 1_000),
            )
            result["energyDefinition"] = "formation_energy_per_atom"
            result["derivedHullComputed"] = False
            return result
        if action == "xrd":
            raise OmniScholarError(
                "local_backend_required",
                "XRD simulation requires the optional pymatgen local backend",
                category="capability",
            )
        raise OmniScholarError(
            "unsupported_capability",
            f"Unsupported materials advanced action: {action}",
            category="capability",
        )

    @staticmethod
    def _result(
        route: str,
        records: list[dict[str, Any]],
        fields: list[str] | None,
        meta: dict[str, Any],
        page: int,
        size: int,
    ) -> dict[str, Any]:
        statuses: dict[str, str] = {}
        if fields:
            for field in fields:
                statuses[field] = (
                    "returned"
                    if any(field in record for record in records)
                    else "missing_from_response"
                )
        total = (
            meta.get("total_doc") if isinstance(meta.get("total_doc"), int) else meta.get("total")
        )
        return {
            "provider": "materials-project",
            "route": route,
            "records": records,
            "total": total,
            "page": page,
            "limit": size,
            "fieldStatus": statuses,
        }

    async def export(
        self, records: list[dict[str, Any]], *, format: str, output_root: Path, relative_path: str
    ) -> dict[str, Any]:
        if format == "json":
            content = (
                json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode()
        elif format == "csv":
            fields = sorted({key for record in records for key in record})
            buffer = io.StringIO(newline="")
            writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for record in records:
                writer.writerow(
                    {
                        key: json.dumps(value, ensure_ascii=False)
                        if isinstance(value, (dict, list))
                        else value
                        for key, value in record.items()
                    }
                )
            content = buffer.getvalue().encode("utf-8-sig")
        elif format == "markdown":
            fields = sorted({key for record in records for key in record})
            lines = [
                "| " + " | ".join(fields) + " |",
                "| " + " | ".join("---" for _ in fields) + " |",
            ]
            for record in records:
                lines.append(
                    "| "
                    + " | ".join(str(record.get(field, "")).replace("|", "\\|") for field in fields)
                    + " |"
                )
            content = ("\n".join(lines) + "\n").encode()
        elif format == "cif":
            if len(records) != 1:
                raise OmniScholarError(
                    "cif_unavailable",
                    "CIF export requires exactly one record",
                    category="validation",
                )
            raw_cif = records[0].get("cif")
            content = (
                raw_cif.encode()
                if isinstance(raw_cif, str)
                else _structure_to_cif(records[0]).encode()
            )
        else:
            raise OmniScholarError(
                "unsupported_format", f"Unsupported export format: {format}", category="validation"
            )
        path = await atomic_write(output_root, relative_path, content)
        return {"path": str(path), "bytes": len(content), "format": format, "records": len(records)}
