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

## Research Gaps

A page that exists but has not been written yet is a research gap, not a summary. Mark it with `research_gap: true` in the frontmatter, keep a short body that says what the page will cover and which source it needs, and leave `status: draft`. The validator counts flagged pages separately: a coverage gate reports `pass` only when the concepts that are **not** research gaps reach `expected`. A one-sentence body without the flag is reported as a thin page.

## Coverage And Sources

`coverage.yaml` records the concept count, the counts per `category` and per `type`, and the coverage gates. Each gate names a glob `pattern` relative to `wiki/`, the `expected` number of concepts (or `null` until known), the `actual` count of matching concepts, the number of those flagged `stubs` (research gaps, only when non-zero), and a `status` derived from `actual - stubs` against `expected` (`pending`, `partial`, `pass`, `fail`). `coverage_status: complete` requires every gate to pass and no research gaps.

`sources.yaml` keeps `version`, `checked_at`, `total_sources` and one entry per primary source with `resource`, `title` and `used_by`. Every `sources[].id` used in a concept must be registered, `used_by` must list exactly the concepts that cite the source, and a registered source that no concept cites is reported. Update both files in the same pull request as the concepts; the validator fails on drift.

## What The Validator Rejects

Beyond frontmatter shape, `tools/validate.py` fails the build on: unregistered or drifting source ids; footnote definitions never referenced; two concepts in one directory with template-identical bodies; a prose sentence repeated across five or more pages (filler); `by_category` or `by_type` not matching the bundle; gate counts or statuses that do not follow from the pages; a `jurisdiction`, `authority_level` or `instrument_status` that is not a quoted string (YAML reads a bare `NO` as `false`); `CITATION.cff` with a `cff-version` other than 1.2.0 or a `version` unequal to `VERSION`; and, once concepts exist, a README or root index still carrying the scaffold banner or a README missing its Licence, NOTICE, CONTRIBUTING or not-legal-advice text. It warns on thin bodies, near-identical bodies, descriptions ending in an ellipsis, self-cancelling relative links, indexes that do not list their pages, registered sources without consumers, and a single `stale_after` shared by every concept.

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
