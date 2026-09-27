#!/usr/bin/env python3
"""Validate an OKF knowledge bundle against its kb.yaml manifest and publication constraints.

Usage:
    python3 tools/validate.py [WIKI_DIR] [--manifest kb.yaml] [--no-coverage] [--no-repo-files]

WIKI_DIR defaults to ``wiki``. The manifest defaults to ``kb.yaml`` next to WIKI_DIR.
``coverage.yaml``, ``sources.yaml``, ``CITATION.cff``, ``VERSION``, ``README.md`` and the root
``wiki/index.md`` next to the manifest are checked when present.

Checks, in addition to OKF frontmatter shape:
- every ``sources[].id`` used by a concept is registered in sources.yaml, and every registered
  source is used by at least one concept;
- coverage.yaml ``by_category`` and ``by_type`` match the bundle, gates match their patterns,
  and a gate's status accounts for concepts flagged ``research_gap: true``;
- footnote definitions are referenced and references are defined;
- no two concepts in one directory have template-identical bodies, and no sentence is repeated
  across many pages (filler detection);
- ``jurisdiction`` is a quoted string (YAML turns a bare ``NO`` into ``false``);
- CITATION.cff keeps ``cff-version`` 1.2.0 and its ``version`` equals VERSION;
- once concepts exist, README.md and wiki/index.md no longer carry the scaffold banner.
"""

from __future__ import annotations

import argparse
import difflib
import fnmatch
import hashlib
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import yaml


RESERVED = {"index.md", "log.md"}
BASE_REQUIRED = {
    "type",
    "title",
    "description",
    "category",
    "status",
    "generated",
    "stale_after",
    "sources",
}
STATUSES = {"draft", "stable", "deprecated"}
COVERAGE_STATUSES = {"planned", "partial", "complete"}
GATE_STATUSES = {"pending", "partial", "pass", "fail"}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
EXTENSION_RE = re.compile(r"^x-[a-z0-9][a-z0-9-]*$")
LINK_RE = re.compile(r"(?<!!)\[[^]]*]\(([^)]+)\)")
FOOTNOTE_RE = re.compile(r"\[\^([^]]+)]")
FOOTNOTE_DEF_RE = re.compile(r"(?m)^\[\^([^]]+)]:")
SCRIPT_RE = re.compile(r"<(?:script|iframe|object|embed)\b", re.IGNORECASE)
SELF_CANCELLING_LINK_RE = re.compile(r"\.\./[^/()\s]+/\.\./")
SCAFFOLD_MARKERS = ("**Scaffold:**", "No concepts have been ingested yet", "no concepts have been ingested yet")
CFF_VERSION = "1.2.0"
MIN_BODY_WORDS = 60          # below this a page must be flagged research_gap or is warned as thin
TEMPLATE_SIMILARITY = 0.92   # difflib ratio above which two bodies in one directory are flagged
FILLER_MIN_WORDS = 8         # sentences shorter than this are ignored by the repeated-sentence check
FILLER_MIN_PAGES = 5         # a sentence repeated in this many pages is flagged as filler

errors: list[str] = []
warnings: list[str] = []


def split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, text
    return text[4:end], text[end + 5 :]


def parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else None
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo:
        return parsed
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return parsed.replace(tzinfo=timezone.utc)
    return None


def load_yaml(path: Path, label: str) -> dict[str, object] | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f"{path}: cannot read {label}: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{path}: {label} must be a mapping")
        return None
    return data


def load_manifest(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        errors.append(f"{path}: manifest not found")
        return None
    manifest = load_yaml(path, "manifest")
    if manifest is None:
        return None
    for field in ("slug", "name", "extension_key", "okf_version"):
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path}: manifest field {field} must be a non-empty string")
    slug = manifest.get("slug")
    if isinstance(slug, str) and not SLUG_RE.match(slug):
        errors.append(f"{path}: slug {slug!r} must be lowercase kebab-case")
    extension = manifest.get("extension_key")
    if isinstance(extension, str) and not EXTENSION_RE.match(extension):
        errors.append(f"{path}: extension_key {extension!r} must look like x-<slug>")
    categories = manifest.get("categories")
    if not isinstance(categories, list) or not categories or not all(isinstance(c, str) for c in categories):
        errors.append(f"{path}: categories must be a non-empty list of strings")
    sections = manifest.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append(f"{path}: sections must be a non-empty list")
    else:
        for position, section in enumerate(sections, 1):
            if not isinstance(section, dict) or not isinstance(section.get("path"), str):
                errors.append(f"{path}: section {position} needs a path")
            elif not isinstance(section.get("title"), str) or not section["title"].strip():
                errors.append(f"{path}: section {section['path']!r} needs a title")
    return manifest


def check_links(path: Path, root: Path, body: str) -> None:
    for raw_target in LINK_RE.findall(body):
        target = unquote(raw_target.split("#", 1)[0].strip())
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        if SELF_CANCELLING_LINK_RE.search(target):
            warnings.append(f"{path}: self-cancelling relative link, simplify it: {raw_target}")
        resolved = root / target.lstrip("/") if target.startswith("/") else path.parent / target
        if target.endswith("/"):
            resolved /= "index.md"
        if not resolved.resolve().is_relative_to(root.resolve()):
            errors.append(f"{path}: internal link escapes bundle: {raw_target}")
        elif not resolved.exists():
            warnings.append(f"{path}: unresolved internal link: {raw_target}")


def check_reserved(path: Path, root: Path, text: str, okf_version: str) -> None:
    front_raw, body = split_frontmatter(text)
    if front_raw is not None:
        if path != root / "index.md":
            errors.append(f"{path}: reserved file must not have frontmatter")
        else:
            try:
                front = yaml.safe_load(front_raw) or {}
            except yaml.YAMLError as exc:
                errors.append(f"{path}: invalid root index frontmatter: {exc}")
                return
            if front != {"okf_version": okf_version}:
                errors.append(f"{path}: root index must declare only okf_version: {okf_version!r}")
            if body.lstrip().startswith("---"):
                errors.append(f"{path}: duplicated frontmatter block rendered as body text")
    elif path == root / "index.md":
        errors.append(f"{path}: root index must declare okf_version: {okf_version!r}")
    check_links(path, root, body)


def check_sources(path: Path, front: dict[str, object], body: str) -> tuple[set[str], dict[str, str]]:
    """Validate sources and footnotes; return (source ids, id -> resource)."""
    raw_sources = front.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        errors.append(f"{path}: sources must be a non-empty list")
        return set(), {}

    source_ids: set[str] = set()
    resources: dict[str, str] = {}
    for position, source in enumerate(raw_sources, 1):
        if not isinstance(source, dict):
            errors.append(f"{path}: source {position} is not a mapping")
            continue
        resource = source.get("resource")
        if not isinstance(resource, str) or not resource.startswith(("http://", "https://", "/", "./", "../")):
            errors.append(f"{path}: source {position} has no valid resource")
        source_id = source.get("id")
        if source_id is not None:
            if not isinstance(source_id, str) or not source_id.strip():
                errors.append(f"{path}: source {position} has an invalid id")
            elif source_id in source_ids:
                errors.append(f"{path}: duplicate source id {source_id!r}")
            else:
                source_ids.add(source_id)
                if isinstance(resource, str):
                    resources[source_id] = resource

    definitions = set(FOOTNOTE_DEF_RE.findall(body))
    references = set(FOOTNOTE_RE.findall(re.sub(r"(?m)^\[\^[^]]+]:.*$", "", body)))
    for reference in references - source_ids:
        errors.append(f"{path}: footnote {reference!r} has no matching sources[].id")
    for definition in definitions - source_ids:
        errors.append(f"{path}: footnote definition {definition!r} has no matching sources[].id")
    for definition in definitions - references:
        errors.append(f"{path}: footnote definition {definition!r} is never referenced in the body")
    if source_ids and not references:
        warnings.append(f"{path}: no footnote references; sourced claims should cite sources[].id")
    return source_ids, resources


def strip_markup(body: str) -> str:
    body = re.sub(r"(?m)^\[\^[^]]+]:.*$", "", body)      # footnote definitions
    body = re.sub(r"\[\^[^]]+]", "", body)               # footnote references
    body = re.sub(r"(?m)^#+ .*$", "", body)              # headings
    body = re.sub(r"```.*?```", "", body, flags=re.S)    # code blocks
    body = re.sub(r"\[([^]]*)]\([^)]*\)", r"\1", body)   # links -> text
    body = re.sub(r"[*_`>|#-]", " ", body)
    return body


def normalise_for_template(body: str, title: str) -> str:
    text = strip_markup(body).lower()
    for token in re.findall(r"[a-z0-9]+", title.lower()):
        if len(token) > 2:
            text = re.sub(rf"\b{re.escape(token)}\b", " ", text)
    text = re.sub(r"\d+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def sentences(body: str) -> list[str]:
    """Prose sentences of the body: list items and link lists are dropped, only punctuated sentences count."""
    prose = "\n".join(line for line in body.split("\n") if not re.match(r"^\s*([-*+]|\d+\.)\s", line))
    text = re.sub(r"\s+", " ", strip_markup(prose))
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) >= FILLER_MIN_WORDS and s.rstrip().endswith((".", "!", "?"))]


class Concept:
    def __init__(self, path: Path, rel: str, front: dict[str, object], body: str) -> None:
        self.path = path
        self.rel = rel
        self.front = front
        self.body = body
        self.category = front.get("category") if isinstance(front.get("category"), str) else "?"
        self.type = front.get("type") if isinstance(front.get("type"), str) else "?"
        self.research_gap = bool(front.get("research_gap"))
        self.word_count = len(strip_markup(body).split())


def check_concept(path: Path, root: Path, text: str, manifest: dict[str, object]) -> tuple[Concept | None, set[str], dict[str, str]]:
    extension_key = str(manifest.get("extension_key", "x-kb"))
    categories = set(manifest.get("categories") or [])

    front_raw, body = split_frontmatter(text)
    if front_raw is None:
        errors.append(f"{path}: missing YAML frontmatter")
        return None, set(), {}
    try:
        front = yaml.safe_load(front_raw)
    except yaml.YAMLError as exc:
        errors.append(f"{path}: invalid YAML frontmatter: {exc}")
        return None, set(), {}
    if not isinstance(front, dict):
        errors.append(f"{path}: frontmatter must be a mapping")
        return None, set(), {}

    missing = (BASE_REQUIRED | {extension_key}) - set(front)
    if missing:
        errors.append(f"{path}: missing required fields: {', '.join(sorted(missing))}")
    if "id" in front:
        errors.append(f"{path}: concept ID is its path; remove redundant id field")
    for other in (key for key in front if key.startswith("x-") and key != extension_key):
        errors.append(f"{path}: unexpected extension {other!r}; this bundle uses {extension_key}")
    for field in ("type", "title", "description"):
        if field in front and (not isinstance(front[field], str) or not front[field].strip()):
            errors.append(f"{path}: {field} must be a non-empty string")
    description = front.get("description")
    if isinstance(description, str) and description.rstrip().endswith(("...", "…")):
        warnings.append(f"{path}: description ends in an ellipsis; write a complete sentence")
    if front.get("status") not in STATUSES:
        errors.append(f"{path}: invalid status {front.get('status')!r}")
    category = front.get("category")
    if category not in categories:
        errors.append(f"{path}: category {category!r} is not declared in the manifest")
    if "research_gap" in front and not isinstance(front["research_gap"], bool):
        errors.append(f"{path}: research_gap must be true or false")

    generated = front.get("generated")
    if not isinstance(generated, dict) or not generated.get("by") or parse_datetime(generated.get("at")) is None:
        errors.append(f"{path}: generated requires by and an offset-aware ISO 8601 at")
    if parse_datetime(front.get("stale_after")) is None:
        errors.append(f"{path}: stale_after must be an ISO 8601 date or offset-aware datetime")

    extension = front.get(extension_key)
    if extension is not None:
        if not isinstance(extension, dict):
            errors.append(f"{path}: {extension_key} must be a mapping")
        else:
            if parse_datetime(extension.get("checked_at")) is None:
                errors.append(f"{path}: {extension_key}.checked_at must be an ISO 8601 date or offset-aware datetime")
            for field in ("jurisdiction", "authority_level", "instrument_status"):
                if field in extension and not isinstance(extension[field], str):
                    errors.append(f"{path}: {extension_key}.{field} must be a quoted string (YAML reads bare NO as false)")

    if front.get("status") == "stable" and not front.get("verified"):
        errors.append(f"{path}: stable concept requires verified metadata")
    if isinstance(extension, dict) and extension.get("presumption_of_conformity") is True:
        if extension.get("ojeu_cited") is not True or not extension.get("ojeu_reference"):
            errors.append(f"{path}: presumption of conformity requires an OJEU citation reference")
    if front.get("status") == "deprecated" and not re.search(r"\]\([^)]+\.md\)", body):
        warnings.append(f"{path}: deprecated concept should link to its replacement")

    if SCRIPT_RE.search(body):
        errors.append(f"{path}: executable or embedded HTML is not allowed")
    source_ids, resources = check_sources(path, front, body)
    check_links(path, root, body)

    concept = Concept(path, path.relative_to(root).with_suffix("").as_posix(), front, body)
    if not concept.research_gap and concept.word_count < MIN_BODY_WORDS:
        warnings.append(f"{path}: body has {concept.word_count} words; expand it or set research_gap: true")
    return concept, source_ids, resources


def check_sections(root: Path, manifest: dict[str, object]) -> None:
    declared: set[str] = set()
    for section in manifest.get("sections") or []:
        if not isinstance(section, dict) or not isinstance(section.get("path"), str):
            continue
        declared.add(section["path"])
        directory = root / section["path"]
        if not directory.is_dir():
            errors.append(f"{directory}: declared section directory is missing")
        elif not (directory / "index.md").is_file():
            errors.append(f"{directory}: declared section has no index.md")
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        if directory.name not in declared:
            warnings.append(f"{directory}: top-level directory is not declared in the manifest sections")


def check_index_completeness(root: Path, concepts: list[Concept]) -> None:
    by_dir: dict[Path, list[Concept]] = defaultdict(list)
    for concept in concepts:
        by_dir[concept.path.parent].append(concept)
    for directory, pages in by_dir.items():
        index = directory / "index.md"
        if not index.is_file():
            errors.append(f"{directory}: directory holds concepts but has no index.md")
            continue
        text = index.read_text(encoding="utf-8")
        for concept in pages:
            if concept.path.name not in text:
                warnings.append(f"{index}: does not list {concept.path.name}")
    for directory in {p.parent for p in by_dir} | set(by_dir):
        index = directory / "index.md"
        if index.is_file():
            text = index.read_text(encoding="utf-8")
            for child in sorted(p for p in directory.iterdir() if p.is_dir() and (p / "index.md").is_file()):
                if f"{child.name}/" not in text:
                    warnings.append(f"{index}: does not list the subsection {child.name}/")


def check_templates(concepts: list[Concept]) -> None:
    by_dir: dict[Path, list[Concept]] = defaultdict(list)
    for concept in concepts:
        by_dir[concept.path.parent].append(concept)
    for directory, pages in by_dir.items():
        if len(pages) < 3:
            continue
        normalised = {c.rel: normalise_for_template(c.body, str(c.front.get("title", ""))) for c in pages}
        seen: dict[str, str] = {}
        for rel, text in normalised.items():
            if not text:
                continue
            digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
            if digest in seen:
                errors.append(f"{directory}: template-identical bodies: {seen[digest]} and {rel}")
            else:
                seen[digest] = rel
        if len(pages) > 250:
            continue
        rels = sorted(normalised)
        flagged: set[tuple[str, str]] = set()
        for i, a in enumerate(rels):
            ta = normalised[a]
            if len(ta) < 80:
                continue
            for b in rels[i + 1 :]:
                tb = normalised[b]
                if len(tb) < 80 or (a, b) in flagged:
                    continue
                matcher = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
                if matcher.quick_ratio() >= TEMPLATE_SIMILARITY and matcher.ratio() >= TEMPLATE_SIMILARITY:
                    flagged.add((a, b))
                    warnings.append(f"{directory}: near-identical bodies ({matcher.ratio():.2f}): {a} and {b}")
    seen_sentences: dict[str, set[str]] = defaultdict(set)
    for concept in concepts:
        if concept.research_gap:
            continue  # stubs legitimately share their gap notice
        for sentence in set(sentences(concept.body)):
            seen_sentences[sentence.lower()].add(concept.rel)
    for sentence, rels in sorted(seen_sentences.items(), key=lambda item: -len(item[1])):
        if len(rels) >= FILLER_MIN_PAGES:
            errors.append(f"filler: the sentence {sentence[:90]!r}... appears in {len(rels)} pages, for example {sorted(rels)[0]}")


def check_uniform_metadata(concepts: list[Concept]) -> None:
    if len(concepts) < 20:
        return
    stale = Counter(str(c.front.get("stale_after")) for c in concepts)
    if len(stale) == 1:
        warnings.append(f"all {len(concepts)} concepts share stale_after {next(iter(stale))}; differentiate by subject volatility")


def gate_status(actual: int, expected: object) -> str:
    if actual <= 0:
        return "pending"
    if isinstance(expected, int):
        if actual == expected:
            return "pass"
        return "partial" if actual < expected else "fail"
    return "partial"


def check_coverage(path: Path, concepts: list[Concept], version: str | None) -> None:
    coverage = load_yaml(path, "coverage manifest")
    if coverage is None:
        return
    if coverage.get("coverage_status") not in COVERAGE_STATUSES:
        errors.append(f"{path}: coverage_status must be one of {sorted(COVERAGE_STATUSES)}")
    if coverage.get("total_concepts") != len(concepts):
        errors.append(f"{path}: total_concepts is {coverage.get('total_concepts')!r}, bundle has {len(concepts)}")
    if version is not None and str(coverage.get("release")) != version:
        warnings.append(f"{path}: release {coverage.get('release')!r} differs from VERSION {version!r}")

    for field, attr in (("by_category", "category"), ("by_type", "type")):
        counted = Counter(getattr(c, attr) for c in concepts)
        declared = coverage.get(field)
        if declared is None:
            if field == "by_category":
                errors.append(f"{path}: by_category is required")
            continue
        if not isinstance(declared, dict):
            errors.append(f"{path}: {field} must be a mapping")
        elif {k: v for k, v in declared.items() if v} != dict(counted):
            errors.append(f"{path}: {field} {dict(declared)!r} does not match bundle counts {dict(counted)!r}")

    gates = coverage.get("gates")
    if gates is None:
        gates = {}
    if not isinstance(gates, dict):
        errors.append(f"{path}: gates must be a mapping")
        return
    all_pass = True
    rels = {c.rel: c for c in concepts}
    for name, gate in gates.items():
        if not isinstance(gate, dict):
            errors.append(f"{path}: gate {name!r} must be a mapping")
            continue
        pattern = gate.get("pattern")
        if not isinstance(pattern, str):
            errors.append(f"{path}: gate {name!r} needs a pattern relative to the wiki root")
            continue
        matching = [rels[r] for r in rels if fnmatch.fnmatchcase(r, pattern)]
        computed = len(matching)
        stubs = sum(1 for c in matching if c.research_gap)
        if gate.get("actual") != computed:
            errors.append(f"{path}: gate {name!r} actual is {gate.get('actual')!r}, bundle has {computed}")
        if stubs and gate.get("stubs") != stubs:
            errors.append(f"{path}: gate {name!r} must declare stubs: {stubs} (concepts flagged research_gap)")
        if "stubs" in gate and gate.get("stubs") != stubs:
            errors.append(f"{path}: gate {name!r} stubs is {gate.get('stubs')!r}, bundle has {stubs}")
        expected = gate.get("expected")
        if expected is not None and (not isinstance(expected, int) or expected < 0):
            errors.append(f"{path}: gate {name!r} expected must be a non-negative integer or null")
        derived = gate_status(computed - stubs, expected)
        if gate.get("status") != derived:
            errors.append(f"{path}: gate {name!r} status is {gate.get('status')!r}, derived {derived!r} from {computed} concepts minus {stubs} research gaps")
        all_pass = all_pass and derived == "pass"
    if coverage.get("coverage_status") == "complete" and not all_pass:
        errors.append(f"{path}: coverage_status complete requires every gate to pass")
    gap_count = sum(1 for c in concepts if c.research_gap)
    if gap_count and coverage.get("coverage_status") == "complete":
        errors.append(f"{path}: coverage_status complete with {gap_count} concepts flagged research_gap")


def check_source_register(path: Path, concepts: list[Concept], used: dict[str, set[str]], resources: dict[str, set[str]]) -> None:
    register = load_yaml(path, "source register")
    if register is None:
        return
    for field in ("version", "checked_at", "total_sources"):
        if field not in register:
            errors.append(f"{path}: missing top-level field {field}")
    sources = register.get("sources")
    if sources is None:
        sources = {}
    if not isinstance(sources, dict):
        errors.append(f"{path}: sources must be a mapping keyed by source id")
        return
    if register.get("total_sources") != len(sources):
        errors.append(f"{path}: total_sources is {register.get('total_sources')!r}, register has {len(sources)}")
    rels = {c.rel for c in concepts}
    for source_id, source in sources.items():
        if not isinstance(source, dict):
            errors.append(f"{path}: source {source_id!r} must be a mapping")
            continue
        if source.get("id") not in (None, source_id):
            errors.append(f"{path}: source {source_id!r} has mismatching id {source.get('id')!r}")
        if not isinstance(source.get("resource"), str):
            errors.append(f"{path}: source {source_id!r} has no resource")
        declared_used = set(source.get("used_by") or [])
        for concept in declared_used - rels:
            warnings.append(f"{path}: source {source_id!r} is used_by unknown concept {concept!r}")
        actual_used = used.get(source_id, set())
        if not actual_used:
            warnings.append(f"{path}: source {source_id!r} is registered but no concept cites it")
        elif declared_used != actual_used:
            missing = sorted(actual_used - declared_used)
            extra = sorted(declared_used - actual_used)
            errors.append(f"{path}: source {source_id!r} used_by drift; missing {missing[:5]}, extra {extra[:5]}")
        if isinstance(source.get("resource"), str) and resources.get(source_id) and source["resource"] not in resources[source_id]:
            warnings.append(f"{path}: source {source_id!r} resource differs from the concepts' resource(s)")
    for source_id, rels_using in sorted(used.items()):
        if source_id not in sources:
            errors.append(f"{path}: source id {source_id!r} is used by {len(rels_using)} concept(s) but not registered, for example {sorted(rels_using)[0]}")


def check_repo_files(base: Path, concept_count: int, version: str | None) -> None:
    citation = base / "CITATION.cff"
    if citation.is_file():
        data = load_yaml(citation, "CITATION.cff")
        if data is not None:
            if str(data.get("cff-version")) != CFF_VERSION:
                errors.append(f"{citation}: cff-version must be {CFF_VERSION} (it is the schema version, not the release)")
            if version is not None and str(data.get("version")) != version:
                errors.append(f"{citation}: version {data.get('version')!r} differs from VERSION {version!r}")
            for field in ("title", "authors", "repository-code", "license", "type", "date-released"):
                if field not in data:
                    errors.append(f"{citation}: missing field {field}")
    if concept_count > 0:
        for name in ("README.md", "wiki/index.md"):
            path = base / name
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for marker in SCAFFOLD_MARKERS:
                if marker in text:
                    errors.append(f"{path}: still carries the scaffold banner ({marker!r}) although the bundle has {concept_count} concepts")
                    break
            if name == "README.md" and version not in (None, "0.0.0") and "Current release: **none yet**" in text:
                errors.append(f"{path}: says no release yet but VERSION is {version}")
        readme = base / "README.md"
        if readme.is_file():
            text = readme.read_text(encoding="utf-8")
            for needle, label in (("## Licence", "Licence section"), ("NOTICE", "NOTICE pointer"), ("CONTRIBUTING.md", "CONTRIBUTING link"), ("not legal advice", "not-legal-advice disclaimer")):
                if needle not in text:
                    errors.append(f"{readme}: missing the {label}")
        root_index = base / "wiki" / "index.md"
        if root_index.is_file() and "General orientation only" not in root_index.read_text(encoding="utf-8"):
            warnings.append(f"{root_index}: missing the general-orientation disclaimer")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("wiki", nargs="?", default="wiki", help="bundle root (default: wiki)")
    parser.add_argument("--manifest", help="kb.yaml path (default: next to the bundle root)")
    parser.add_argument("--no-coverage", action="store_true", help="skip coverage.yaml and sources.yaml checks")
    parser.add_argument("--no-repo-files", action="store_true", help="skip CITATION.cff, README.md and banner checks")
    args = parser.parse_args()

    root = Path(args.wiki).resolve()
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")
    manifest_path = Path(args.manifest).resolve() if args.manifest else root.parent / "kb.yaml"
    base = manifest_path.parent
    manifest = load_manifest(manifest_path)
    if manifest is None:
        for error in errors:
            print(f"error:   {error}")
        return 1
    okf_version = str(manifest.get("okf_version", "0.2"))

    concepts: list[Concept] = []
    used: dict[str, set[str]] = defaultdict(set)
    resources: dict[str, set[str]] = defaultdict(set)
    all_files = sorted(path for path in root.rglob("*") if path.is_file() or path.is_symlink())
    for path in all_files:
        if path.is_symlink():
            errors.append(f"{path}: symlinks are not allowed")
            continue
        if path.suffix.lower() != ".md":
            errors.append(f"{path}: only Markdown files are allowed in the bundle")
            continue
        text = path.read_text(encoding="utf-8")
        if path.name in RESERVED:
            check_reserved(path, root, text, okf_version)
        else:
            concept, ids, res = check_concept(path, root, text, manifest)
            if concept is not None:
                concepts.append(concept)
                for source_id in ids:
                    used[source_id].add(concept.rel)
                for source_id, resource in res.items():
                    resources[source_id].add(resource)

    check_sections(root, manifest)
    check_index_completeness(root, concepts)
    check_templates(concepts)
    check_uniform_metadata(concepts)

    version_path = base / "VERSION"
    version = version_path.read_text(encoding="utf-8").strip() if version_path.is_file() else None
    if not args.no_coverage:
        coverage_path = base / "coverage.yaml"
        if coverage_path.is_file():
            check_coverage(coverage_path, concepts, version)
        register_path = base / "sources.yaml"
        if register_path.is_file():
            check_source_register(register_path, concepts, used, resources)
    if not args.no_repo_files:
        check_repo_files(base, len(concepts), version)

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error:   {error}")

    print(f"\n{len(all_files)} files ({len(concepts)} concepts), {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
