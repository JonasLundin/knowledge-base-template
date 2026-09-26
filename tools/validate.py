#!/usr/bin/env python3
"""Validate an OKF knowledge bundle against its kb.yaml manifest and publication constraints.

Usage:
    python3 tools/validate.py [WIKI_DIR] [--manifest kb.yaml] [--no-coverage]

WIKI_DIR defaults to ``wiki``. The manifest defaults to ``kb.yaml`` next to WIKI_DIR.
``coverage.yaml`` and ``sources.yaml`` next to the manifest are checked when present.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
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
SCRIPT_RE = re.compile(r"<(?:script|iframe|object|embed)\b", re.IGNORECASE)

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
    elif path == root / "index.md":
        errors.append(f"{path}: root index must declare okf_version: {okf_version!r}")
    check_links(path, root, body)


def check_sources(path: Path, front: dict[str, object], body: str) -> None:
    raw_sources = front.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        errors.append(f"{path}: sources must be a non-empty list")
        return

    source_ids: set[str] = set()
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

    references = set(FOOTNOTE_RE.findall(body))
    definitions = set(re.findall(r"(?m)^\[\^([^]]+)]:", body))
    for reference in references - source_ids:
        errors.append(f"{path}: footnote {reference!r} has no matching sources[].id")
    for definition in definitions - source_ids:
        errors.append(f"{path}: footnote definition {definition!r} has no matching sources[].id")


def check_concept(path: Path, root: Path, text: str, manifest: dict[str, object]) -> str | None:
    """Validate one concept page and return its category when readable."""
    extension_key = str(manifest.get("extension_key", "x-kb"))
    categories = set(manifest.get("categories") or [])

    front_raw, body = split_frontmatter(text)
    if front_raw is None:
        errors.append(f"{path}: missing YAML frontmatter")
        return None
    try:
        front = yaml.safe_load(front_raw)
    except yaml.YAMLError as exc:
        errors.append(f"{path}: invalid YAML frontmatter: {exc}")
        return None
    if not isinstance(front, dict):
        errors.append(f"{path}: frontmatter must be a mapping")
        return None

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
    if front.get("status") not in STATUSES:
        errors.append(f"{path}: invalid status {front.get('status')!r}")
    category = front.get("category")
    if category not in categories:
        errors.append(f"{path}: category {category!r} is not declared in the manifest")

    generated = front.get("generated")
    if not isinstance(generated, dict) or not generated.get("by") or parse_datetime(generated.get("at")) is None:
        errors.append(f"{path}: generated requires by and an offset-aware ISO 8601 at")
    if parse_datetime(front.get("stale_after")) is None:
        errors.append(f"{path}: stale_after must be an ISO 8601 date or offset-aware datetime")

    extension = front.get(extension_key)
    if extension is not None:
        if not isinstance(extension, dict):
            errors.append(f"{path}: {extension_key} must be a mapping")
        elif parse_datetime(extension.get("checked_at")) is None:
            errors.append(f"{path}: {extension_key}.checked_at must be an ISO 8601 date or offset-aware datetime")

    if front.get("status") == "stable" and not front.get("verified"):
        errors.append(f"{path}: stable concept requires verified metadata")
    if front.get("type") == "Standard" and isinstance(extension, dict):
        if extension.get("presumption_of_conformity") is True:
            if extension.get("ojeu_cited") is not True or not extension.get("ojeu_reference"):
                errors.append(f"{path}: presumption of conformity requires an OJEU citation reference")

    if SCRIPT_RE.search(body):
        errors.append(f"{path}: executable or embedded HTML is not allowed")
    check_sources(path, front, body)
    check_links(path, root, body)
    return category if isinstance(category, str) else None


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


def gate_status(actual: int, expected: object) -> str:
    if actual == 0:
        return "pending"
    if isinstance(expected, int):
        if actual == expected:
            return "pass"
        return "partial" if actual < expected else "fail"
    return "partial"


def check_coverage(path: Path, concepts: dict[str, str], version: str | None) -> None:
    coverage = load_yaml(path, "coverage manifest")
    if coverage is None:
        return
    if coverage.get("coverage_status") not in COVERAGE_STATUSES:
        errors.append(f"{path}: coverage_status must be one of {sorted(COVERAGE_STATUSES)}")
    if coverage.get("total_concepts") != len(concepts):
        errors.append(f"{path}: total_concepts is {coverage.get('total_concepts')!r}, bundle has {len(concepts)}")
    if version is not None and str(coverage.get("release")) != version:
        warnings.append(f"{path}: release {coverage.get('release')!r} differs from VERSION {version!r}")

    counted: dict[str, int] = {}
    for category in concepts.values():
        counted[category] = counted.get(category, 0) + 1
    declared = coverage.get("by_category")
    if declared is None:
        declared = {}
    if not isinstance(declared, dict):
        errors.append(f"{path}: by_category must be a mapping")
    elif {k: v for k, v in declared.items() if v} != counted:
        errors.append(f"{path}: by_category {declared!r} does not match bundle counts {counted!r}")

    gates = coverage.get("gates")
    if gates is None:
        gates = {}
    if not isinstance(gates, dict):
        errors.append(f"{path}: gates must be a mapping")
        return
    all_pass = True
    for name, gate in gates.items():
        if not isinstance(gate, dict):
            errors.append(f"{path}: gate {name!r} must be a mapping")
            continue
        pattern = gate.get("pattern")
        if not isinstance(pattern, str):
            errors.append(f"{path}: gate {name!r} needs a pattern relative to the wiki root")
            continue
        computed = sum(1 for concept in concepts if fnmatch.fnmatchcase(concept, pattern))
        if gate.get("actual") != computed:
            errors.append(f"{path}: gate {name!r} actual is {gate.get('actual')!r}, bundle has {computed}")
        expected = gate.get("expected")
        if expected is not None and (not isinstance(expected, int) or expected < 0):
            errors.append(f"{path}: gate {name!r} expected must be a non-negative integer or null")
        derived = gate_status(computed, expected)
        if gate.get("status") != derived:
            errors.append(f"{path}: gate {name!r} status is {gate.get('status')!r}, derived {derived!r}")
        all_pass = all_pass and derived == "pass"
    if coverage.get("coverage_status") == "complete" and not all_pass:
        errors.append(f"{path}: coverage_status complete requires every gate to pass")


def check_source_register(path: Path, concepts: dict[str, str]) -> None:
    register = load_yaml(path, "source register")
    if register is None:
        return
    sources = register.get("sources")
    if sources is None:
        sources = {}
    if not isinstance(sources, dict):
        errors.append(f"{path}: sources must be a mapping keyed by source id")
        return
    if register.get("total_sources") != len(sources):
        errors.append(f"{path}: total_sources is {register.get('total_sources')!r}, register has {len(sources)}")
    for source_id, source in sources.items():
        if not isinstance(source, dict):
            errors.append(f"{path}: source {source_id!r} must be a mapping")
            continue
        if source.get("id") not in (None, source_id):
            errors.append(f"{path}: source {source_id!r} has mismatching id {source.get('id')!r}")
        for concept in source.get("used_by") or []:
            if concept not in concepts:
                warnings.append(f"{path}: source {source_id!r} is used_by unknown concept {concept!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("wiki", nargs="?", default="wiki", help="bundle root (default: wiki)")
    parser.add_argument("--manifest", help="kb.yaml path (default: next to the bundle root)")
    parser.add_argument("--no-coverage", action="store_true", help="skip coverage.yaml and sources.yaml checks")
    args = parser.parse_args()

    root = Path(args.wiki).resolve()
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")
    manifest_path = Path(args.manifest).resolve() if args.manifest else root.parent / "kb.yaml"
    manifest = load_manifest(manifest_path)
    if manifest is None:
        for error in errors:
            print(f"error:   {error}")
        return 1
    okf_version = str(manifest.get("okf_version", "0.2"))

    concepts: dict[str, str] = {}
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
            category = check_concept(path, root, text, manifest)
            concepts[path.relative_to(root).with_suffix("").as_posix()] = category or "?"

    check_sections(root, manifest)

    if not args.no_coverage:
        version_path = manifest_path.parent / "VERSION"
        version = version_path.read_text(encoding="utf-8").strip() if version_path.is_file() else None
        coverage_path = manifest_path.parent / "coverage.yaml"
        if coverage_path.is_file():
            check_coverage(coverage_path, concepts, version)
        register_path = manifest_path.parent / "sources.yaml"
        if register_path.is_file():
            check_source_register(register_path, concepts)

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error:   {error}")

    print(f"\n{len(all_files)} files ({len(concepts)} concepts), {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
