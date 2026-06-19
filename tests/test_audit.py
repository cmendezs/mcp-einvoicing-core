"""Tests for mcp_einvoicing_core.audit — CHECK 6 and load_rates."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from mcp_einvoicing_core.audit import (
    KNOWN_SHARED_HELPERS,
    SEVERITY_BLOCKING,
    SEVERITY_OK,
    TaxRate,
    load_rates,
    run_check_known_shared_helpers,
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
            source_dir=src, package_label="test-pkg",
        )
        assert result.passed
        assert any(f.severity == SEVERITY_OK for f in result.findings)

    def test_reimplemented_helper_is_blocking(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "utils.py").write_text("def format_amount(x): return str(x)\n")
        result = run_check_known_shared_helpers(
            source_dir=src, package_label="test-pkg",
        )
        assert not result.passed
        blocking = [f for f in result.findings if f.severity == SEVERITY_BLOCKING]
        assert len(blocking) == 1
        assert blocking[0].symbol == "format_amount"

    def test_multiple_reimplementations(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "helpers.py").write_text(
            "def format_amount(x): pass\ndef xml_escape(s): pass\n"
        )
        result = run_check_known_shared_helpers(
            source_dir=src, package_label="test-pkg",
        )
        blocking = [f for f in result.findings if f.severity == SEVERITY_BLOCKING]
        assert len(blocking) == 2

    def test_nested_files_detected(self, tmp_path: Path) -> None:
        nested = tmp_path / "src" / "deep" / "nested"
        nested.mkdir(parents=True)
        (nested / "util.py").write_text("def scrub(v): return v\n")
        result = run_check_known_shared_helpers(
            source_dir=tmp_path / "src", package_label="test-pkg",
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
            source_dir=tmp_path / "nonexistent", package_label="test-pkg",
        )
        assert result.skipped

    def test_private_functions_ignored(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "x.py").write_text("def _format_amount(x): pass\n")
        result = run_check_known_shared_helpers(
            source_dir=src, package_label="test-pkg",
        )
        assert result.passed

    def test_known_helpers_set_is_nonempty(self) -> None:
        assert len(KNOWN_SHARED_HELPERS) >= 10


# ---------------------------------------------------------------------------
# load_rates
# ---------------------------------------------------------------------------


class TestLoadRates:

    def test_valid_rates_toml(self, tmp_path: Path) -> None:
        toml = tmp_path / "rates.toml"
        toml.write_text(textwrap.dedent("""\
            [rates.standard]
            value = "0.22"
            effective_from = "2013-10-01"
            source = "https://example.com/law.pdf"

            [rates.reduced]
            value = "0.10"
            effective_from = "2020-01-01"
            source = "https://example.com/reduced.pdf"
            category = "food"
        """))
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
        toml.write_text(textwrap.dedent("""\
            [rates.bad]
            value = "0.19"
        """))
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
