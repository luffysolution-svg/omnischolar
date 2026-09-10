# Failure and scientific boundaries

- Missing credentials: point to `data.materialsProject.apiKey`, `apiKeyEnv`, or `MP_API_KEY`; never request a secret in a prompt or note.
- Permission or entitlement errors: report the source limitation. Do not switch providers silently.
- HTTP 429 or timeout: honor provider backoff, keep pagination bounded, and return verified partial results rather than looping.
- Missing property: preserve whether it was unrequested, unavailable, inapplicable, or failed.
- Unsupported filter: ask for a supported formulation; never silently drop a scientific constraint.
- XRD without the optional local backend: report `local_backend_required`. Do not guess a server route or synthesize a curve.
- Invalid structure for CIF: report the rejected field/shape without inventing coordinates, occupancies, or symmetry.
- Export conflict: preserve the existing user file and require an explicit alternative or overwrite decision.
- Corrupt cache or malformed provider data: reject it; do not invent values or expand remote work automatically.

Preserve energy correction and functional distinctions. Report spin, normalization, coordinate convention, and frequency/energy units when relevant. Calculated values and generated XRD are not experimental measurements.
