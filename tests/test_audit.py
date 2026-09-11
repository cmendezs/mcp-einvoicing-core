"""Tests for mcp_einvoicing_core.audit — CHECK 6 and load_rates."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

from mcp_einvoicing_core.audit import (
    KNOWN_SHARED_HELPERS,
    SEVERITY_BLOCKING,
    SEVERITY_OK,
    TaxRate,
    _read_core_version_spec,
    load_rates,
    run_check_known_shared_helpers,
    run_check_no_internal_references,
)

# ---------------------------------------------------------------------------
# CHECK 6 — Known shared helpers
# ---------------------------------------------------------------------------


class TestCheckKnownSharedHelpers:
    def test_clean_package_passes(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "tools.py").write_text("def my_custom_tool(): pass\n")
        result = run_check_known_shared_helpers(
            source_dir=src,
            package_label="test-pkg",
        )
        assert result.passed
        assert any(f.severity == SEVERITY_OK for f in result.findings)

    def test_reimplemented_helper_is_blocking(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "utils.py").write_text("def format_amount(x): return str(x)\n")
        result = run_check_known_shared_helpers(
            source_dir=src,
            package_label="test-pkg",
        )
        assert not result.passed
        blocking = [f for f in result.findings if f.severity == SEVERITY_BLOCKING]
        assert len(blocking) == 1
        assert blocking[0].symbol == "format_amount"

    def test_multiple_reimplementations(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "helpers.py").write_text("def format_amount(x): pass\ndef xml_escape(s): pass\n")
        result = run_check_known_shared_helpers(
            source_dir=src,
            package_label="test-pkg",
        )
        blocking = [f for f in result.findings if f.severity == SEVERITY_BLOCKING]
        assert len(blocking) == 2

    def test_nested_files_detected(self, tmp_path: Path) -> None:
        nested = tmp_path / "src" / "deep" / "nested"
        nested.mkdir(parents=True)
        (nested / "util.py").write_text("def scrub(v): return v\n")
        result = run_check_known_shared_helpers(
            source_dir=tmp_path / "src",
            package_label="test-pkg",
        )
        blocking = [f for f in result.findings if f.severity == SEVERITY_BLOCKING]
        assert len(blocking) == 1
        assert blocking[0].symbol == "scrub"

    def test_extra_helpers(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "x.py").write_text("def my_special_helper(): pass\n")
        result = run_check_known_shared_helpers(
            source_dir=src,
            package_label="test-pkg",
            extra_helpers=frozenset({"my_special_helper"}),
        )
        blocking = [f for f in result.findings if f.severity == SEVERITY_BLOCKING]
        assert len(blocking) == 1

    def test_missing_source_dir_skips(self, tmp_path: Path) -> None:
        result = run_check_known_shared_helpers(
            source_dir=tmp_path / "nonexistent",
            package_label="test-pkg",
        )
        assert result.skipped

    def test_private_functions_ignored(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "x.py").write_text("def _format_amount(x): pass\n")
        result = run_check_known_shared_helpers(
            source_dir=src,
            package_label="test-pkg",
        )
        assert result.passed

    def test_known_helpers_set_is_nonempty(self) -> None:
        assert len(KNOWN_SHARED_HELPERS) >= 10


# ---------------------------------------------------------------------------
# load_rates
# ---------------------------------------------------------------------------


class TestReadCoreVersionSpec:
    """CHECK 4 helper — must not be fooled by a comment line preceding the
    real dependency entry (regression: SG and AE's pyproject.toml both carry
    a two-line comment explaining the uv #9811 pin, and the comment itself
    contains the substring "mcp-einvoicing-core")."""

    def test_reads_plain_dependency_line(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent(
                """
                [project]
                dependencies = [
                    "mcp-einvoicing-core>=1.24.0,<2.0.0",
                ]
                """
            )
        )
        assert _read_core_version_spec(pyproject) == ">=1.24.0,<2.0.0"

    def test_ignores_preceding_comment_with_package_name(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            textwrap.dedent(
                """
                [project]
                # The upper-bound pin on mcp-einvoicing-core is mandatory: uv bug #9811 strips version
                # pins from built wheel metadata, so this is the only protection downstream consumers have.
                dependencies = [
                    "mcp-einvoicing-core>=1.24.0,<2.0.0",
                ]
                """
            )
        )
        assert _read_core_version_spec(pyproject) == ">=1.24.0,<2.0.0"

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert _read_core_version_spec(tmp_path / "does-not-exist.toml") is None

    def test_no_dependency_returns_none(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\ndependencies = ["some-other-package>=1.0.0"]\n')
        assert _read_core_version_spec(pyproject) is None


class TestLoadRates:
    def test_valid_rates_toml(self, tmp_path: Path) -> None:
        toml = tmp_path / "rates.toml"
        toml.write_text(
            textwrap.dedent("""\
            [rates.standard]
            value = "0.22"
            effective_from = "2013-10-01"
            source = "https://example.com/law.pdf"

            [rates.reduced]
            value = "0.10"
            effective_from = "2020-01-01"
            source = "https://example.com/reduced.pdf"
            category = "food"
        """)
        )
        rates = load_rates(toml)
        assert len(rates) == 2
        assert isinstance(rates[0], TaxRate)
        assert rates[0].value == "0.22"
        assert rates[1].category == "food"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_rates(tmp_path / "missing.toml")

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        toml = tmp_path / "rates.toml"
        toml.write_text(
            textwrap.dedent("""\
            [rates.bad]
            value = "0.19"
        """)
        )
        with pytest.raises(ValueError, match="missing required fields"):
            load_rates(toml)

    def test_empty_rates_section_raises(self, tmp_path: Path) -> None:
        toml = tmp_path / "rates.toml"
        toml.write_text("[other]\nkey = 1\n")
        with pytest.raises(ValueError, match="No \\[rates\\] section"):
            load_rates(toml)

    def test_non_table_entry_raises(self, tmp_path: Path) -> None:
        toml = tmp_path / "rates.toml"
        toml.write_text('[rates]\nstandard = "not a table"\n')
        with pytest.raises(ValueError, match="expected a table"):
            load_rates(toml)


# ---------------------------------------------------------------------------
# CHECK_PUBLIC_HYGIENE — no references to the private orchestration repo
# ---------------------------------------------------------------------------


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)


class TestCheckNoInternalReferences:
    def test_clean_repo_passes(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text("Nothing to see here.\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)

        result = run_check_no_internal_references(repo_root=tmp_path)

        assert result.blocking_count == 0
        assert any(f.tag == "[OK]" for f in result.findings)

    def test_context_library_reference_is_blocking(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text(
            "See context-library/countries/xx.md for the full reference.\n"
        )
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)

        result = run_check_no_internal_references(repo_root=tmp_path)

        assert result.blocking_count == 1
        finding = result.findings[0]
        assert finding.severity == SEVERITY_BLOCKING
        assert finding.symbol == "README.md:1"
        assert "context-library/" in finding.message

    def test_reports_one_finding_per_match_with_line_numbers(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "NOTES.md").write_text(
            "line one\nsee sub-agents/mcp-audit-fr.md\nline three\nand .claude/skills/publish/SKILL.md too\n"
        )
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)

        result = run_check_no_internal_references(repo_root=tmp_path)

        assert result.blocking_count == 2
        symbols = {f.symbol for f in result.findings}
        assert symbols == {"NOTES.md:2", "NOTES.md:4"}

    def test_audit_vs_core_py_is_self_excluded(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        audit_dir = tmp_path / "audit"
        audit_dir.mkdir()
        (audit_dir / "audit_vs_core.py").write_text(
            "# defines the check; legitimately says context-library/ and sub-agents/\n"
        )
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)

        result = run_check_no_internal_references(repo_root=tmp_path)

        assert result.blocking_count == 0

    def test_binary_and_oversized_files_are_skipped_not_erroring(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "spec.bin").write_bytes(b"\x00\x01context-library/\xff\xfe")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)

        result = run_check_no_internal_references(repo_root=tmp_path)

        assert result.blocking_count == 0

    def test_extra_excluded_paths_are_skipped(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "LEGACY.md").write_text("context-library/ mentioned deliberately here.\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)

        result = run_check_no_internal_references(
            repo_root=tmp_path, extra_excluded_paths=frozenset({"LEGACY.md"})
        )

        assert result.blocking_count == 0

    def test_not_a_git_repo_skips_rather_than_blocks(self, tmp_path: Path) -> None:
        result = run_check_no_internal_references(repo_root=tmp_path)

        assert result.skipped
        assert result.blocking_count == 0

    def test_this_repo_itself_passes(self) -> None:
        """Dogfooding: mcp-einvoicing-core is a public repo too."""
        repo_root = Path(__file__).resolve().parent.parent
        result = run_check_no_internal_references(repo_root=repo_root)

        assert result.blocking_count == 0, [
            f"{f.symbol}: {f.message}" for f in result.findings if f.severity == SEVERITY_BLOCKING
        ]
