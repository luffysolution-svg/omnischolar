---
name: scientific-figure
description: Generate or edit scientific illustration drafts with OmniScholar, including reference-guided and multi-reference work, or use Ai4Scholar for its declared figure actions. Use for mechanisms, graphical abstracts, workflows, apparatus diagrams, concept art, critique, or vectorization.
license: MIT
compatibility: Requires OmniScholar and a configured image provider. Generation is paid; reference upload additionally requires explicit external-upload authorization.
---

# Scientific figure workflow

Follow the user's language. Generated content is an illustration draft, never experimental evidence or measured data.

## Define the figure contract

Confirm the scientific message, audience, figure type, required entities and labels, causal arrows, units, language, aspect ratio, background, output format, and whether reference images may leave the machine. Ask only when an assumption would change scientific meaning, privacy, cost, or layout.

## Route by declared capability

1. Call `omnischolar_image_models` and use only descriptors where `usable=true` and the exact requested capability is declared.
2. A catalog-visible model with no declared capability remains unusable. Never infer text-to-image, edit, or multi-reference support from a model name.
3. Use `omnischolar_image_generate` for text-to-image or declared image-to-image generation.
4. Use `omnischolar_image_edit` for edit operations; multiple references require an explicit `multi-reference` declaration.
5. Use `ai4scholar_figure` only for its declared actions and explicit paid authorization.
6. Use `omnischolar_image_service` with `action=status` for local configuration status or `action=job` only when a configured provider exposes that job contract.

If the chosen provider is absent, disabled, lacks credentials, lacks entitlement, or has no usable capability pin/curated descriptor, stop and report the exact blocker. Offer another configured provider only after confirming the same capability and informing the user. Atlas and custom providers require explicit endpoint/model contracts. Do not treat a successful model listing as generation entitlement.

## Upload and cost

- Paid generation requires both configuration enablement and `allowPaid=true` on the current call.
- Any reference image requires both configuration enablement and `allowExternalUpload=true` on the current call.
- Use only user-authorized or Agent-generated references. Never substitute a private image.
- Start with one economical image and the smallest useful dimensions. Do not blindly retry an ambiguous paid submission.
- Provider URLs and task identifiers are transport details; use saved local artifacts and do not expose signed URLs.

## Prompt and review

Specify subject/claim, composition, scientific constraints, visual language, output constraints, and exclusions. Prefer deterministic plotting code for quantitative charts, spectra, microscopy measurements, diffraction traces, and axes.

After generation, inspect spelling, notation, units, molecular/crystal geometry, arrows, legends, scale bars, panel order, and hallucinated details. State whether deterministic finishing or domain-expert review is still required.
