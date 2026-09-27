import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


MANIFEST = textwrap.dedent(
    """\
    manifest_version: 1
    okf_version: "0.2"
    slug: test
    name: Test Knowledge Base
    description: Validation fixture.
    extension_key: x-test
    categories: [law, requirement, glossary]
    sections:
      - path: law
        title: Law
        description: Fixture section.
    """
)

BODY = """
# Summary

The fixture concept explains one requirement in original words so that the body is long enough to pass
the thin-page check, describes who it binds, when it applies, and which primary source establishes it,
and it cites that source with a footnote.[^test-source] A second paragraph adds context about scope,
exclusions and the dates on which the requirement starts to apply, so the page reads as a real summary.

[^test-source]: Test source.
"""

def concept(name="Test requirement", source="test-source", body=BODY, extra="", category="requirement"):
    lines = [
        "---",
        "type: Requirement",
        f"title: {name}",
        f"description: A validation fixture about {name.lower()}.",
        f"category: {category}",
        "tags: [test]",
        "status: draft",
        "generated: { by: process:test, at: 2026-09-26T00:00:00Z }",
        "stale_after: 2026-12-26T00:00:00Z",
    ]
    if extra:
        lines.append(extra.strip())
    lines += [
        "sources:",
        f"  - id: {source}",
        "    resource: https://example.eu/source",
        "    title: Test source",
        "x-test:",
        "  jurisdiction: EU",
        "  checked_at: 2026-09-26T00:00:00Z",
        "---",
    ]
    return "\n".join(lines) + "\n" + body.replace("test-source", source)


VALID_CONCEPT = concept()

COVERAGE_OK = textwrap.dedent(
    """\
    version: 1
    release: 0.0.0
    baseline: '2026-09-26'
    coverage_status: partial
    review_status: unverified
    total_concepts: 1
    by_category:
      requirement: 1
    by_type:
      Requirement: 1
    gates:
      law_pages:
        pattern: 'law/*'
        expected: 2
        actual: 1
        status: partial
    """
)

SOURCES_OK = textwrap.dedent(
    """\
    version: 1
    checked_at: '2026-09-26T00:00:00Z'
    total_sources: 1
    sources:
      test-source:
        resource: https://example.eu/source
        title: Test source
        used_by:
          - law/test
    """
)

CITATION_OK = textwrap.dedent(
    """\
    cff-version: 1.2.0
    title: Test
    type: dataset
    authors: [{family-names: Lundin, given-names: Jonas}]
    repository-code: https://example.eu
    license: CC-BY-4.0
    version: 0.0.0
    date-released: 2026-09-26
    """
)


class ValidatorTest(unittest.TestCase):
    def run_validator(self, concepts, manifest=MANIFEST, coverage=None, sources=None, citation=None, readme=None, section_index=True):
        if isinstance(concepts, str):
            concepts = {"test.md": concepts}
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "kb.yaml").write_text(manifest, encoding="utf-8")
            (base / "VERSION").write_text("0.0.0\n", encoding="utf-8")
            if coverage is not None:
                (base / "coverage.yaml").write_text(coverage, encoding="utf-8")
            if sources is not None:
                (base / "sources.yaml").write_text(sources, encoding="utf-8")
            if citation is not None:
                (base / "CITATION.cff").write_text(citation, encoding="utf-8")
            if readme is not None:
                (base / "README.md").write_text(readme, encoding="utf-8")
            root = base / "wiki"
            (root / "law").mkdir(parents=True)
            (root / "index.md").write_text(
                '---\nokf_version: "0.2"\n---\n\n# Test bundle\n\n> **General orientation only:** fixture.\n\n- [Law](law/)\n',
                encoding="utf-8",
            )
            if section_index:
                listing = "\n".join(f"- [{n}]({n})" for n in concepts)
                (root / "law" / "index.md").write_text(f"# Law\n\n{listing}\n", encoding="utf-8")
            for name, text in concepts.items():
                (root / "law" / name).write_text(text, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(Path(__file__).with_name("validate.py")), str(root)],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_accepts_valid_concept(self) -> None:
        result = self.run_validator(VALID_CONCEPT, coverage=COVERAGE_OK, sources=SOURCES_OK, citation=CITATION_OK)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 errors, 0 warnings", result.stdout)

    def test_rejects_missing_type(self) -> None:
        result = self.run_validator(VALID_CONCEPT.replace("type: Requirement\n", ""))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required fields: type", result.stdout)

    def test_requires_manifest_extension_key(self) -> None:
        result = self.run_validator(VALID_CONCEPT.replace("x-test:", "x-other:"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required fields: x-test", result.stdout)
        self.assertIn("unexpected extension 'x-other'", result.stdout)

    def test_rejects_undeclared_category(self) -> None:
        result = self.run_validator(concept(category="product"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("category 'product' is not declared", result.stdout)

    def test_requires_section_index(self) -> None:
        result = self.run_validator(VALID_CONCEPT, section_index=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("declared section has no index.md", result.stdout)

    def test_coverage_detects_drift(self) -> None:
        drifted = COVERAGE_OK.replace("total_concepts: 1", "total_concepts: 5").replace("status: partial", "status: pass")
        result = self.run_validator(VALID_CONCEPT, coverage=drifted)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("total_concepts is 5, bundle has 1", result.stdout)
        self.assertIn("status is 'pass', derived 'partial'", result.stdout)

    def test_coverage_by_type_and_research_gap(self) -> None:
        stub = concept(extra="research_gap: true\n")
        coverage = COVERAGE_OK.replace("Requirement: 1", "Requirement: 2").replace("actual: 1", "actual: 1")
        result = self.run_validator(stub, coverage=coverage)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("by_type", result.stdout)
        self.assertIn("must declare stubs: 1", result.stdout)
        honest = COVERAGE_OK.replace("actual: 1\n    status: partial", "actual: 1\n    stubs: 1\n    status: pending").replace("Requirement: 1", "Requirement: 1")
        result = self.run_validator(stub, coverage=honest)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_unregistered_and_unused_sources(self) -> None:
        result = self.run_validator(concept(source="other-source"), sources=SOURCES_OK)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source id 'other-source' is used by 1 concept(s) but not registered", result.stdout)
        self.assertIn("source 'test-source' is registered but no concept cites it", result.stdout)

    def test_used_by_drift(self) -> None:
        result = self.run_validator(VALID_CONCEPT, sources=SOURCES_OK.replace("law/test", "law/somewhere-else"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("used_by drift", result.stdout)

    def test_unreferenced_footnote_definition(self) -> None:
        body = BODY.replace("footnote.[^test-source]", "footnote.")
        result = self.run_validator(concept(body=body))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is never referenced in the body", result.stdout)

    def test_template_identical_bodies(self) -> None:
        pages = {f"country-{i}.md": concept(name=f"Country {i}") for i in range(3)}
        result = self.run_validator(pages)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("template-identical bodies", result.stdout)

    def test_repeated_filler_sentence(self) -> None:
        filler = "This page sets out statutory requirements, obligations and supervisory mandates under the framework."
        pages = {}
        for i in range(5):
            body = BODY.replace("A second paragraph adds context", f"Topic {i} differs here in wording number {i} for the {'x' * i} case. {filler} A second paragraph adds context")
            pages[f"page-{i}.md"] = concept(name=f"Page {i}", body=body)
        result = self.run_validator(pages)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("filler: the sentence", result.stdout)

    def test_jurisdiction_must_be_string(self) -> None:
        result = self.run_validator(VALID_CONCEPT.replace("jurisdiction: EU", "jurisdiction: NO"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be a quoted string", result.stdout)

    def test_citation_and_banner(self) -> None:
        bad_citation = CITATION_OK.replace("cff-version: 1.2.0", "cff-version: 0.1.0")
        readme = "# Test\n\n> **Scaffold:** nothing here.\n"
        result = self.run_validator(VALID_CONCEPT, citation=bad_citation, readme=readme)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cff-version must be 1.2.0", result.stdout)
        self.assertIn("still carries the scaffold banner", result.stdout)
        self.assertIn("missing the Licence section", result.stdout)

    def test_rejects_bad_manifest(self) -> None:
        result = self.run_validator(VALID_CONCEPT, manifest=MANIFEST.replace("extension_key: x-test", "extension_key: test"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must look like x-<slug>", result.stdout)


if __name__ == "__main__":
    unittest.main()
