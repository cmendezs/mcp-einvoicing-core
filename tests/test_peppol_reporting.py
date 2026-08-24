"""Tests for Peppol EUSR/TSR reporting (CORE-PEPPOL-REPORT-1).

Uses the vendored ``specs/peppol/reporting/{eusr,tsr}/example/*.xml`` fixtures
directly, per the plan's verification step 7. Requires the ``[xslt2]``
optional extra (``saxonche``, present in the ``dev`` extras group) — the
bundled Schematron stylesheets are XSLT 2.0.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from mcp_einvoicing_core.peppol.reporting import (
    load_eusr_codelist,
    load_tsr_codelist,
    parse_eusr,
    parse_tsr,
    peppol_reporting_validator,
    validate_eusr,
    validate_tsr,
)
from mcp_einvoicing_core.peppol.reporting_tools import register_peppol_reporting_tools

_SPECS_DIR = Path(__file__).parent.parent / "specs" / "peppol" / "reporting"
_EUSR_EXAMPLES_DIR = _SPECS_DIR / "eusr" / "example"
_TSR_EXAMPLES_DIR = _SPECS_DIR / "tsr" / "example"

_HAS_EXAMPLES = _EUSR_EXAMPLES_DIR.is_dir() and _TSR_EXAMPLES_DIR.is_dir()
requires_examples = pytest.mark.skipif(
    not _HAS_EXAMPLES, reason="vendored specs/peppol/reporting example fixtures not present"
)

pytest.importorskip("saxonche", reason="Schematron validation requires the [xslt2] extra")


@pytest.fixture()
def eusr_full_xml() -> bytes:
    return (_EUSR_EXAMPLES_DIR / "end-user-statistics-reporting-1.xml").read_bytes()


@pytest.fixture()
def eusr_empty_xml() -> bytes:
    return (_EUSR_EXAMPLES_DIR / "end-user-statistics-reporting-empty.xml").read_bytes()


@pytest.fixture()
def tsr_xml() -> bytes:
    return (_TSR_EXAMPLES_DIR / "transaction-statistics-2.xml").read_bytes()


@requires_examples
class TestParseEusr:
    def test_parses_header_and_full_set(self, eusr_full_xml: bytes) -> None:
        report = parse_eusr(eusr_full_xml)
        assert report.customization_id == "urn:fdc:peppol.eu:edec:trns:end-user-statistics-report:1.1"
        assert report.header.reporter_id.value == "POP000360"
        assert report.header.report_period.start_date == "2022-01-01"
        assert report.full_set.sending_end_users == 5
        assert report.full_set.receiving_end_users == 3
        assert report.full_set.sending_or_receiving_end_users == 6

    def test_parses_subsets(self, eusr_full_xml: bytes) -> None:
        report = parse_eusr(eusr_full_xml)
        assert len(report.subsets) == 6
        first = report.subsets[0]
        assert first.type == "PerDT-PR"
        assert len(first.keys) == 2
        assert first.keys[0].meta_scheme_id == "DT"

    def test_parses_empty_report(self, eusr_empty_xml: bytes) -> None:
        report = parse_eusr(eusr_empty_xml)
        assert report.full_set.sending_end_users == 0
        assert report.subsets == []


@requires_examples
class TestParseTsr:
    def test_parses_header_and_total(self, tsr_xml: bytes) -> None:
        report = parse_tsr(tsr_xml)
        assert report.customization_id == (
            "urn:fdc:peppol.eu:edec:trns:transaction-statistics-reporting:1.0"
        )
        assert report.total.incoming == 19
        assert report.total.outgoing == 17

    def test_parses_subtotals(self, tsr_xml: bytes) -> None:
        report = parse_tsr(tsr_xml)
        assert len(report.subtotals) == 10
        first = report.subtotals[0]
        assert first.type == "PerTP"
        assert first.keys[0].meta_scheme_id == "TP"


@requires_examples
class TestValidateEusr:
    @pytest.mark.parametrize(
        "filename",
        [
            "end-user-statistics-reporting-1.xml",
            "end-user-statistics-reporting-2.xml",
            "end-user-statistics-reporting-appendix1.xml",
            "end-user-statistics-reporting-appendix2.xml",
            "end-user-statistics-reporting-appendix3.xml",
            "end-user-statistics-reporting-empty.xml",
            "end-user-statistics-reporting-minimal.xml",
        ],
    )
    def test_vendored_examples_pass(self, filename: str) -> None:
        xml_bytes = (_EUSR_EXAMPLES_DIR / filename).read_bytes()
        result = validate_eusr(xml_bytes)
        assert result.is_valid, result.errors

    def test_malformed_xml_fails_xsd(self) -> None:
        result = validate_eusr(b"<NotAnEusr/>")
        assert result.is_valid is False

    def test_xsd_failure_short_circuits_schematron(self) -> None:
        # Missing FullSet entirely -> XSD failure, before Schematron ever runs.
        result = validate_eusr(
            b'<EndUserStatisticsReport xmlns="urn:fdc:peppol:end-user-statistics-report:1.1"/>'
        )
        assert result.is_valid is False
        assert result.errors


@requires_examples
class TestValidateTsr:
    @pytest.mark.parametrize(
        "filename",
        [
            "transaction-statistics-2.xml",
            "transaction-statistics-3.xml",
            "transaction-statistics-4.xml",
            "transaction-statistics-appendix1.xml",
            "transaction-statistics-appendix2.xml",
            "transaction-statistics-minimal.xml",
        ],
    )
    def test_vendored_examples_pass(self, filename: str) -> None:
        xml_bytes = (_TSR_EXAMPLES_DIR / filename).read_bytes()
        result = validate_tsr(xml_bytes)
        assert result.is_valid, result.errors

    def test_business_rule_violation_detected(self, tsr_xml: bytes) -> None:
        broken = tsr_xml.replace(b"<Incoming>19</Incoming>", b"<Incoming>999</Incoming>", 1)
        result = validate_tsr(broken)
        assert result.is_valid is False
        assert any("subtotal" in e.text.lower() for e in result.errors)


@requires_examples
class TestPeppolReportingValidatorFactory:
    def test_eusr_kind(self, eusr_full_xml: bytes) -> None:
        validator = peppol_reporting_validator("eusr")
        result = validator.validate(eusr_full_xml)
        assert result.is_valid

    def test_tsr_kind(self, tsr_xml: bytes) -> None:
        validator = peppol_reporting_validator("tsr")
        result = validator.validate(tsr_xml)
        assert result.is_valid

    def test_unknown_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown reporting kind"):
            peppol_reporting_validator("bogus")


class TestBundledCodelists:
    def test_load_eusr_codelist(self) -> None:
        codelist = load_eusr_codelist("subset_type")
        assert len(codelist.rows) > 0

    def test_load_tsr_codelist(self) -> None:
        codelist = load_tsr_codelist("subtotal_type")
        assert len(codelist.rows) > 0

    def test_unknown_eusr_codelist_raises(self) -> None:
        with pytest.raises(KeyError):
            load_eusr_codelist("bogus")


class _FakeMCP:
    def __init__(self) -> None:
        self.registered: dict[str, object] = {}

    def tool(self):
        def decorator(fn):
            self.registered[fn.__name__] = fn
            return fn

        return decorator


@requires_examples
class TestRegisterPeppolReportingTools:
    def test_registers_expected_tool_set(self) -> None:
        mcp = _FakeMCP()
        register_peppol_reporting_tools(mcp)
        assert set(mcp.registered) == {"validate_eusr_report", "validate_tsr_report"}

    def test_validate_eusr_report_tool(self, eusr_full_xml: bytes) -> None:
        mcp = _FakeMCP()
        register_peppol_reporting_tools(mcp)
        result = mcp.registered["validate_eusr_report"](base64.b64encode(eusr_full_xml).decode())
        assert result["is_valid"] is True

    def test_validate_tsr_report_tool(self, tsr_xml: bytes) -> None:
        mcp = _FakeMCP()
        register_peppol_reporting_tools(mcp)
        result = mcp.registered["validate_tsr_report"](base64.b64encode(tsr_xml).decode())
        assert result["is_valid"] is True
