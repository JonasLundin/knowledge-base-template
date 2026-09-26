# Release Notes Standard (KB-RNS-01)

## 1. Purpose and scope

This standard sets the mandatory structure, versioning principles and verification requirements for every release of this knowledge base. It is shared by all knowledge bases built from [JonasLundin/knowledge-base-template](https://github.com/JonasLundin/knowledge-base-template).

The bundle bridges primary legal or normative sources, technical standards and engineering practice. Release notes therefore have to give traceability to the sources, accuracy about their legal status, and actionable clarity for engineers, security teams and compliance officers.

---

## 2. Governance and versioning principles

### 2.1 Semantic versioning for knowledge bundles

Releases follow Semantic Versioning 2.0.0 (`vMAJOR.MINOR.PATCH`), mapped to how the covered corpus changes:

1. **MAJOR (`vX.0.0`) - epochal milestones or breaking taxonomy changes:**
   - a statutory application date or equivalent programme milestone that changes what the bundle describes;
   - a breaking change to the OKF schema version or to `kb.yaml`;
   - a reorganisation of the concept hierarchy that requires downstream consumers to migrate.
2. **MINOR (`v0.X.0`) - source reconciliations and significant concept additions:**
   - newly published secondary legislation, rule versions, guidance revisions or standards drafts;
   - new concept clusters, roles, procedures or jurisdictions.
3. **PATCH (`v0.0.X`) - errata and maintenance:**
   - typos, broken links, stale metadata dates;
   - clarifications that do not alter the reading of a source;
   - validator, test and CI maintenance.

### 2.2 Dual audience

Every release note balances the legal or normative context (citations to the primary sources and their status) with the engineering and operational impact (what downstream teams should change).

---

## 3. Required sections

Every release note (`releases/v<VERSION>.md`) contains these sections in this order:

```markdown
# Release Notes: v<MAJOR>.<MINOR>.<PATCH> — <Theme/Headline>

## 1. Release Metadata
## 2. Executive Summary & Context
## 3. Normative Drift & Source Reconciliation Ledger
## 4. Concept & Content Changes (Keep a Changelog)
    ### Added
    ### Changed
    ### Deprecated
    ### Removed
    ### Fixed
    ### Security & Compliance
## 5. Implementation & Operational Guidance (Downstream Impact)
## 6. Verification, Validation & Integrity Evidence
## 7. Migration Guide & Breaking Changes
## 8. Upcoming Milestones & Roadmap
```

### 3.1 Release metadata
Version, ISO 8601 release date, commit and tag, motivating milestone, OKF schema version, and the counts of concepts and sources.

### 3.2 Executive summary and context
The catalyst for the release and the main takeaways for the audience the bundle serves.

### 3.3 Normative drift and source reconciliation ledger
A table of every source in `sources.yaml` that was added, updated or re-checked, with previous and current dates and a summary of the drift.

### 3.4 Concept and content changes
Grouped under the Keep a Changelog categories: Added, Changed, Deprecated, Removed, Fixed, Security & Compliance.

### 3.5 Implementation and operational guidance
Direct instructions for engineering, security and compliance practitioners.

### 3.6 Verification, validation and integrity evidence
Reproducible commands and their exact output:
- `python3 tools/validate.py wiki` must report 0 errors and 0 warnings;
- `python3 -m unittest tools/test_validate.py` must pass;
- the concept count must match `coverage.yaml`.

### 3.7 Migration guide and breaking changes
Deprecated structures or semantic shifts, with remediation steps.

### 3.8 Upcoming milestones and roadmap
The next dated events in the covered corpus.

---

## 4. Release artefacts

A release synchronises four artefacts:

1. the standalone release file `releases/v<VERSION>.md`;
2. an entry in `CHANGELOG.md` under `[<VERSION>] - <YYYY-MM-DD>`;
3. the version manifests `VERSION`, `CITATION.cff` and `coverage.yaml` (`release`);
4. the GitHub release, published with `gh release create v<VERSION> -F releases/v<VERSION>.md`.
