# Release Notes: v<MAJOR>.<MINOR>.<PATCH> — <Theme / Headline>

## 1. Release Metadata

| Field | Value |
|---|---|
| **Version** | `v<MAJOR>.<MINOR>.<PATCH>` |
| **Release Date** | `<YYYY-MM-DD>` |
| **Git Commit / Tag** | `<COMMIT_HASH>` / `v<MAJOR>.<MINOR>.<PATCH>` |
| **Milestone** | `<the regulatory, standards or programme event that motivates the release>` |
| **OKF Schema Version** | `0.2` |
| **Total Sources** | `<SOURCE_COUNT>` |
| **Total Concepts** | `<CONCEPT_COUNT>` |

---

## 2. Executive Summary & Context

<!-- Two to four paragraphs: the catalyst, its grounding in the primary sources, and the key takeaways for downstream consumers. -->

---

## 3. Normative Drift & Source Reconciliation Ledger

| Source ID | Issuing Authority | Title | Version / Ref | Previous Date | Current Date | Drift / Change Summary |
|---|---|---|---|---|---|---|
| `<source-id>` | `<Authority>` | `<Document Title>` | `<vX.Y>` | `<YYYY-MM-DD>` | `<YYYY-MM-DD>` | `<Specific changes reconciled>` |

---

## 4. Concept & Content Changes

### Added
- `<Concept Title>` (`<file-path>`): `<Brief description>`

### Changed
- `<Concept Title>` (`<file-path>`): `<Brief description>`

### Deprecated
- `<Item>`: `<Reason>`

### Removed
- `<Item>`: `<Reason>`

### Fixed
- `<Concept Title>` (`<file-path>`): `<Correction details>`

### Security & Compliance
- `<Topic>`: `<Implications>`

---

## 5. Implementation & Operational Guidance (Downstream Impact)

1. **Security and incident response teams:**
   - `<Action item>`
2. **Product development and architecture:**
   - `<Action item>`
3. **Legal and compliance:**
   - `<Action item>`

---

## 6. Verification, Validation & Integrity Evidence

### 6.1 OKF Schema & Bundle Integrity
```bash
$ python3 tools/validate.py wiki
<OUTPUT>
```

### 6.2 Automated Unit Testing
```bash
$ python3 -m unittest tools/test_validate.py
<OUTPUT>
```

---

## 7. Migration Guide & Breaking Changes

<!-- Breaking changes to concept taxonomies or schema and the migration steps for consumers. If none, state "No breaking changes." -->

---

## 8. Upcoming Milestones & Roadmap

- **`<DATE>`:** `<Milestone Description>`
- **`<DATE>`:** `<Milestone Description>`
