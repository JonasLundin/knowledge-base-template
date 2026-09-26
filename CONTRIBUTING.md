# Contributing

Contributions should improve accuracy, coverage, or source freshness without turning the bundle into legal advice.

## Content Rules

1. Condense the essence in original wording.
2. Cite the primary source and the exact article, paragraph, annex point, section, work item, or official reference.
3. Distinguish binding law, non-binding guidance, drafts, final standards, and standards whose reference is cited in the OJEU.
4. Do not copy full instruments, long passages, standards clauses, tables, figures, PDFs, or spreadsheets.
5. Do not submit private compliance evidence, personal data, credentials, or confidential material.
6. Keep generated content `status: draft` and omit `verified`; maintainers add verification only after checking the source.
7. Retain superseded concepts as `deprecated` pages linked to their replacement.
8. Record a missing official source as a research gap; do not fill it by inference.

## Bundle Manifest

`kb.yaml` at the repository root declares the bundle: its slug, name, the extension key every concept must carry (`x-<slug>`), the allowed `category` values, and the top-level sections under `wiki/`. Every declared section has an `index.md`. Add a category or section by editing the manifest in the same pull request.

## Concept Shape

Every non-reserved concept is Markdown with OKF v0.2 YAML frontmatter. Replace `x-<slug>` with the `extension_key` from `kb.yaml`:

```yaml
---
type: Requirement
title: Example requirement
description: One sentence describing the concept.
category: requirement
tags: [example]
status: draft
generated: { by: human:your-id, at: 2026-09-26T00:00:00Z }
stale_after: 2026-12-26T00:00:00Z
sources:
  - id: primary-source
    resource: https://example.eu/official-source
    title: Official source title
x-<slug>:
  jurisdiction: EU
  authority_level: binding
  checked_at: 2026-09-26T00:00:00Z
---
```

The path relative to `wiki/`, without `.md`, is the concept ID. Do not add a separate `id` field. `index.md` and `log.md` are reserved and normally have no frontmatter; the root `wiki/index.md` declares only `okf_version`.

Use footnote labels matching `sources[].id` for sourced body claims.

## Coverage And Sources

`coverage.yaml` records the concept count, the count per category, and the coverage gates. Each gate names a glob `pattern` relative to `wiki/`, the `expected` number of concepts (or `null` until known), the `actual` count, and a `status` derived from them (`pending`, `partial`, `pass`, `fail`). `sources.yaml` lists every primary source with the concepts that use it. The validator checks both against the bundle; update them in the same pull request as the concepts.

## Pull Requests

State:

- what changed;
- the controlling primary source;
- the source's legal or standards status;
- its reuse terms;
- the date checked;
- affected concepts, coverage entries, and source register entries.

Run before opening a pull request:

```sh
python3 -m unittest tools/test_validate.py
python3 tools/validate.py wiki
```
