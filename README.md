# Knowledge Base Template

Template for regulatory and standards knowledge bases published as [Open Knowledge Format (OKF)](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) bundles that [Meerkat](https://github.com/zegit-zoo/meerkat) serves as CLI, MCP, or HTTP. It is the shape extracted from [CRA-knowledge-base](https://github.com/JonasLundin/CRA-knowledge-base), generalised so every bundle in the series validates the same way.

A bundle built from this template holds concise original summaries with provision-level citations to primary sources. It never reproduces full legal instruments, rules, guidance documents, or standards.

## What The Template Provides

| Path | Purpose |
|---|---|
| `kb.yaml` | Bundle manifest: slug, name, extension key (`x-<slug>`), allowed categories, top-level sections |
| `wiki/` | The OKF bundle. `index.md` declares `okf_version`; every declared section has an `index.md` |
| `tools/validate.py` | Manifest-driven validator: frontmatter, extension key, categories, sections, links, footnotes, coverage gates, source register |
| `tools/test_validate.py` | Unit tests for the validator |
| `coverage.yaml` | Concept counts and coverage gates (`pattern`, `expected`, `actual`, `status`) |
| `sources.yaml` | Register of every primary source and the concepts that use it |
| `.github/workflows/validate.yml` | CI: tests and validation on every push and pull request |
| `docs/standards/` | Release-notes standard `KB-RNS-01` and its template |
| `CONTRIBUTING.md`, `SECURITY.md`, `NOTICE`, `LICENSE`, `CITATION.cff` | Contribution rules, reporting channel, source reuse terms, CC BY 4.0, citation metadata |

## Create A New Knowledge Base

1. Create the repository from this template.
2. Edit `kb.yaml`: `slug`, `name`, `description`, `extension_key` (`x-<slug>`), the `categories` the corpus needs, and the `sections` under `wiki/`.
3. Create `wiki/<section>/index.md` for every declared section, describing what belongs there. Nested directories may carry their own `index.md`.
4. Rewrite `README.md`: scope, intended corpus, source policy, disclaimer, related bundles.
5. Update `CITATION.cff` (title, URLs), `NOTICE` (reuse terms of the source families the bundle cites), and `coverage.yaml` (gates with `expected` counts where the corpus is finite, `null` otherwise).
6. Set repository topics and enable private vulnerability reporting, which `SECURITY.md` relies on.
7. Run the checks and commit. Ingestion starts afterwards, one sourced concept at a time.

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m unittest tools/test_validate.py
python3 tools/validate.py wiki
```

## Conventions Every Bundle Shares

- The concept ID is the path under `wiki/` without `.md`; there is no `id` field.
- Every concept carries the manifest's extension key with at least `checked_at`; other `x-*` keys are rejected.
- Agent-generated content stays `status: draft` until a human verifies it against the cited source. `stable` requires `verified`.
- A standard claims presumption of conformity only with an OJEU citation reference.
- A missing official source is recorded as a research gap, never filled by inference.
- Superseded material is kept and marked `deprecated`, not deleted.
- `coverage.yaml` and `sources.yaml` are updated in the same pull request as the concepts; the validator fails on drift.

## Use With Meerkat

```sh
mk --kb-dir . search "<term>"
mk --kb-dir . show <section>/<concept>
mk --kb-dir . list --category law
mk --kb-dir . mcp serve
mk --kb-dir . http serve --port 4004
```

The Markdown remains usable without Meerkat or any other tool.

## The Series

- [CRA-knowledge-base](https://github.com/JonasLundin/CRA-knowledge-base): Regulation (EU) 2024/2847, the origin of this template
- [NIS2-knowledge-base](https://github.com/JonasLundin/NIS2-knowledge-base): Directive (EU) 2022/2555 and its national transpositions
- [CVD-knowledge-base](https://github.com/JonasLundin/CVD-knowledge-base): coordinated vulnerability disclosure, the CVE Program, CSAF, VEX and scoring
- [AI-Act-knowledge-base](https://github.com/JonasLundin/AI-Act-knowledge-base): Regulation (EU) 2024/1689 as amended
- [Conformity-Assessment-knowledge-base](https://github.com/JonasLundin/Conformity-Assessment-knowledge-base): the New Legislative Framework, modules, accreditation and notified bodies
- [Software-Supply-Chain-knowledge-base](https://github.com/JonasLundin/Software-Supply-Chain-knowledge-base): SBOM formats, attestation, provenance and VEX
- [NIST-CSF-knowledge-base](https://github.com/JonasLundin/NIST-CSF-knowledge-base): NIST Cybersecurity Framework 2.0

## Licence

Original structure, summaries, and metadata are licensed under [CC BY 4.0](LICENSE). Source documents and standards retain their own terms; see [NOTICE](NOTICE).

This project is independent and is not affiliated with or endorsed by Google Cloud or Meerkat.
