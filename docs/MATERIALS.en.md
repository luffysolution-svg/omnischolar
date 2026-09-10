# Materials and chemistry data

[简体中文](MATERIALS.md)

## Materials Project

Materials Project uses these tools:

| Tool | Use |
|---|---|
| `materials_capabilities` | Show supported data types, fields, and filters without a network call |
| `materials_search` | Filter summary records by formula, elements, chemical system, stability, and related fields |
| `materials_route_search` | Query specialized collections such as thermo |
| `materials_get` | Retrieve one material by ID and data type |
| `materials_advanced` | Retrieve phase data and, with a local backend, calculate XRD |
| `materials_export` | Save existing results as JSON, CSV, Markdown, or CIF |

Example:

```json
{
  "schemaVersion": 1,
  "data": {
    "materialsProject": {
      "enabled": true,
      "apiKeyEnv": "OMNISCHOLAR_MATERIALS_PROJECT_API_KEY",
      "maxPages": 5
    }
  }
}
```

Keep formulas, element sets, chemical systems, material IDs, and task IDs distinct. Each collection accepts different filters; call `materials_capabilities` before building a specialized query.

CIF export uses lattice and site data returned by the service and checks numeric values, occupancy, and coordinates. The exported P1 structure is an exchange representation, not a new symmetry analysis. Computed stability also does not establish experimental synthesizability.

XRD needs an additional local calculation backend. Without it, `materials_advanced` returns `local_backend_required` rather than creating a plausible-looking diffraction curve.

## CAS Common Chemistry

CAS queries are enabled only when the config includes an endpoint and request/response description supplied by the service provider. An API key or website login alone is not enough.

Without that information, `chemical_sources` reports `contract_blocked`; `chemical_search` and `chemical_get` do not guess an endpoint.

CAS data remains subject to CAS licensing, including non-commercial restrictions where applicable.
