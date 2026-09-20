---
name: literature-reading
description: Interpret SCI papers with bounded evidence, Zotero reading records, structured single-paper analyses, targeted figure/formula/knowledge reading, and compact multi-paper comparisons or reviews.
license: MIT
---

# SCI literature reading

Follow the language of the user's latest request. Keep stable field names and analysis types in English, but write headings, explanations, tables, and conclusions in the user's language. Preserve paper titles, DOI strings, formulas, chemical names, gene names, and instrument/model names unless translation is explicitly requested.

## Output locations

- MinerU Markdown, assets, copied PDF, and `zotero-reading-record.md` belong to the managed per-paper publication directory.
- Single-paper analyses use `omnischolar_analysis` with `analysisType=full-read` or `analysisType=targeted-reading` and are saved under the configured `Analysis/Single` directory.
- Multi-paper analyses use `analysisType=compare` or `analysisType=review` and are saved under the configured `Analysis/Multi` directory.
- Never write analysis content into the managed MinerU Markdown file. Use the analysis tool so source fingerprints, relative links, and conflict handling are preserved.

## Source and reading-record policy

1. Match the Zotero parent by DOI first, then normalized title/year/author. Stop on ambiguity.
2. Use `zotero_item` with `mode=item` for identity. Use `mode=aggregate` when notes, annotations, or attachment selection are needed.
3. Run `omnischolar_sync` with `action=plan` before parsing or refreshing a paper.
4. After parsing, use the generated source PDF and `source/zotero-reading-record.md` when available. Zotero notes and PDF annotations are personal reading records, not independent paper evidence.
5. Separate every answer into original evidence, author interpretation, model interpretation, user reading record, and uncertainty.

## Single-paper `full-read` template

Use this for a complete SCI-paper reading. The saved document must cover:

1. bibliographic information and paper type;
2. one-sentence summary;
3. research background, gap, question, and hypothesis/objective;
4. core innovation and contribution, with comparison to prior work when evidence exists;
5. materials, samples, datasets, instruments, controls, variables, and experimental conditions;
6. method and research design, including statistics, models, parameters, and reproducibility details;
7. main results with quantitative values and figure/table references;
8. paper conclusion, applicability, and limitations;
9. reference/evidence index with paper section, page, figure/table/formula, and stable local link;
10. a short `Zotero 阅读记录` navigation item that links to `source/zotero-reading-record.md`. Do not copy the note or annotation bodies into `full-read`; the source reading record is the canonical page for them.

Do not fill unavailable experimental conditions, statistics, or sample information from general knowledge. Write `not reported`, `not available`, or `uncertain`.

## Single-paper `targeted-reading` template

Use this when the user asks about a mechanism, method, result, limitation, figure, table, equation, concept, or relationship to existing knowledge. Retrieve only the relevant evidence and include:

- user question and scope;
- relevant figures, tables, schemes, and equations;
- exact or bounded evidence with locators;
- visual observation, caption, author claim, and model interpretation as separate fields;
- a link to relevant existing knowledge-base notes, prior saved analyses, and the Zotero reading record when they are available; do not duplicate long note/annotation bodies;
- links to related papers and whether the relation is support, contradiction, extension, or merely topical similarity;
- unresolved questions and confidence.

For extracted figures, tables, and formulas:

- Build a compact two-column Markdown table for figures and tables. The left column is `预览` and the right column is `图表名称、原文位置与分析解读`.
- Do not put Obsidian image width-alias syntax such as `![[path/to/figure.png|260]]` directly inside a Markdown table cell: the `|260` is parsed as an extra table column. Use the original MinerU asset with an image embed without a width alias: `![[Literatures/<paper>/assets/image-1.jpg]]`. Because the embed points directly to the original MinerU asset, clicking the image opens that original asset; do not add another pipe-based alias inside the table.
- Keep the table exactly two columns. Each extracted image/panel gets its own table row: one original MinerU image embed in the left cell and four clearly separated ordered items in the right cell: `1. 图表标题`、`2. 原文位置`、`3. 作者原文表述`、`4. 图表解读`. Add visible line breaks between the four items. Repeat the shared figure context when several panels belong to one figure, but do not group multiple images into one left cell or create extra table columns.
- For tables, keep the left cell compact with a collapsible or bounded table preview; do not put a very wide table inside the right cell.
- In the right column, keep separate lines for object name, source section/page, author caption, visual or tabular observation, and interpretation. Do not turn a caption into an unsupported scientific conclusion.
- Render important equations as an ordered list. Each item must contain the equation in block math `$$ ... $$`, followed by variables, purpose, assumptions/conditions, and the paper-specific interpretation. Never show escaped formula source inside backticks.
- If a figure caption or formula was not extracted reliably, say so and link to the PDF/source section instead of guessing.

Do not regenerate the full paper reading unless the user asks for it.

## Multi-paper `compare` template

Use for a user-selected set of papers. This is a comparison, not a claim of exhaustive literature coverage.

- State the comparison question and dimensions first.
- Confirm paper identity, DOI, year, journal, and Zotero key.
- Use a compact evidence matrix. Prefer one dimension per row and one paper per column; split the matrix into multiple small tables when it becomes too wide.
- Required dimensions normally include research question, material/sample/dataset, method/design, key conditions, main outcome, limitation, and evidence locator.
- Follow the matrix with agreements, contradictions, condition-dependent differences, methodological effects, and remaining gaps.
- Never merge conclusions because titles are similar; verify population/materials, conditions, outcome definitions, and uncertainty.

## Multi-paper `review` template

Use for a topic-level narrative or systematic/scoping review. State the review mode, question, corpus, time range, search/selection scope, and whether the result is exhaustive. Then provide:

1. corpus overview;
2. thematic or methodological taxonomy;
3. compact evidence tables;
4. progress and trends;
5. consensus and controversies;
6. bias, evidence limitations, and missing research;
7. conclusion and future directions;
8. per-paper source and evidence index.

Do not call a bounded user-selected set a systematic review unless a systematic search and selection protocol was actually performed.

## Sources and links

Do not add your own duplicate `Sources` section. `omnischolar_analysis` appends one canonical `## Sources` section containing Obsidian links to the MinerU document, copied PDF, and `zotero-reading-record.md`. Use those links for navigation instead of manually constructing relative paths.

Do not include YAML frontmatter in the `content` passed to `omnischolar_analysis`; the tool writes the canonical analysis frontmatter. If a model supplies frontmatter anyway, it must be removed before writing.

## Update and follow-up workflow

For a follow-up question about a previously read paper:

1. Reuse the existing context only as a bounded working set.
2. Check `omnischolar_sync` status/plan and the source fingerprint.
3. Retrieve only missing sections, figures, formulas, annotations, or related-paper evidence.
4. State what is new, changed, unchanged, and still uncertain.
5. Write a new targeted analysis or update the existing analysis through `omnischolar_analysis`; never silently overwrite a user-modified file.

For a changed PDF, mark the previous analysis as requiring review and regenerate only after the new source version has been verified.

## Context discipline

- Use `omnischolar_focus` before broad reading.
- Use `omnischolar_locate` for exact phrases, numbers, identifiers, formulas, and claims.
- Use `omnischolar_read` with bounded cursors for full sections.
- Use `omnischolar_context` only for selected evidence and follow-up continuity.
- Never put a complete paper, complete Zotero aggregate, or unbounded tool response into the model context.
