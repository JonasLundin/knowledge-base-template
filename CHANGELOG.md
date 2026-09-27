# Changelog

## [Unreleased]

### Added
- Validator hardening (2026-09-27), after six populated bundles passed the old checks while carrying template-filled pages, invented citations and drifting registers: unregistered and drifting `sources[].id`, unused registered sources, unreferenced footnote definitions, `by_type` reconciliation, `research_gap: true` with per-gate `stubs` so gates cannot pass on stubs, template-identical and near-identical bodies per directory, prose sentences repeated across five or more pages, thin bodies, `description` ellipses, quoted-string checks for `jurisdiction` and related fields, self-cancelling relative links, index completeness, uniform `stale_after`, `CITATION.cff` `cff-version` and `version`, scaffold banners and mandatory README sections once concepts exist. Fifteen unit tests.
- Scaffolded the bundle from [JonasLundin/knowledge-base-template](https://github.com/JonasLundin/knowledge-base-template): manifest, validator, coverage and source registers, section indexes, licence, notices and contribution rules. No concepts ingested yet.
