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

VALID_CONCEPT = textwrap.dedent(
    """\
    ---
    type: Requirement
    title: Test requirement
    description: A validation fixture.
    category: requirement
    tags: [test]
    status: draft
    generated: { by: process:test, at: 2026-09-26T00:00:00Z }
    stale_after: 2026-12-26T00:00:00Z
    sources:
      - id: test-source
        resource: https://example.eu/source
        title: Test source
    x-test:
      jurisdiction: EU
      checked_at: 2026-09-26T00:00:00Z
    ---

    # Summary

    Test claim.[^test-source]

    [^test-source]: Test source.
    """
)

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
    gates:
      law_pages:
        pattern: 'law/*'
        expected: 2
        actual: 1
        status: partial
    """
)


class ValidatorTest(unittest.TestCase):
    def run_validator(
        self,
        concept: str,
        manifest: str = MANIFEST,
        coverage: str | None = None,
        section_index: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "kb.yaml").write_text(manifest, encoding="utf-8")
            (base / "VERSION").write_text("0.0.0\n", encoding="utf-8")
            if coverage is not None:
                (base / "coverage.yaml").write_text(coverage, encoding="utf-8")
            root = base / "wiki"
            (root / "law").mkdir(parents=True)
            (root / "index.md").write_text('---\nokf_version: "0.2"\n---\n\n# Test bundle\n', encoding="utf-8")
            if section_index:
                (root / "law" / "index.md").write_text("# Law\n", encoding="utf-8")
            (root / "law" / "test.md").write_text(concept, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(Path(__file__).with_name("validate.py")), str(root)],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_accepts_valid_concept(self) -> None:
        result = self.run_validator(VALID_CONCEPT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 errors", result.stdout)

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
        result = self.run_validator(VALID_CONCEPT.replace("category: requirement", "category: product"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("category 'product' is not declared", result.stdout)

    def test_requires_section_index(self) -> None:
        result = self.run_validator(VALID_CONCEPT, section_index=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("declared section has no index.md", result.stdout)

    def test_coverage_consistent(self) -> None:
        result = self.run_validator(VALID_CONCEPT, coverage=COVERAGE_OK)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_coverage_detects_drift(self) -> None:
        drifted = COVERAGE_OK.replace("total_concepts: 1", "total_concepts: 5").replace("status: partial", "status: pass")
        result = self.run_validator(VALID_CONCEPT, coverage=drifted)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("total_concepts is 5, bundle has 1", result.stdout)
        self.assertIn("status is 'pass', derived 'partial'", result.stdout)

    def test_rejects_bad_manifest(self) -> None:
        result = self.run_validator(VALID_CONCEPT, manifest=MANIFEST.replace("extension_key: x-test", "extension_key: test"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must look like x-<slug>", result.stdout)


if __name__ == "__main__":
    unittest.main()
