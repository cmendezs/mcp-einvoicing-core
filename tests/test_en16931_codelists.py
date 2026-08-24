"""Tests for the EN 16931 semantic code-list parser and lookup functions
(CORE-EN16931-CODELIST-1). Uses synthetic Genericode fixtures written to
tmp_path, mirroring test_peppol_codelists.py, so these tests do not depend
on the deployer-supplied specs/en16931/codelists/ directory being present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_einvoicing_core import en16931_codelists as codelists
from mcp_einvoicing_core.en16931_codelist_tools import register_en16931_codelist_tools


def _write_gc(
    directory: Path,
    basename: str,
    *,
    version: str = "2026-05-15",
    rows: list[dict[str, str]],
    columns: list[str] | None = None,
) -> Path:
    cols = columns or ["Code", "Name"]
    column_xml = "\n".join(
        f'    <Column Id="{c}" Use="required"><ShortName>{c}</ShortName><Data Type="string" /></Column>'
        for c in cols
    )
    row_xml_parts = []
    for row in rows:
        values = "\n".join(
            f'      <Value ColumnRef="{k}"><SimpleValue>{v}</SimpleValue></Value>'
            for k, v in row.items()
        )
        row_xml_parts.append(f"    <Row>\n{values}\n    </Row>")
    rows_xml = "\n".join(row_xml_parts)

    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<gc:CodeList xmlns:gc="http://docs.oasis-open.org/codelist/ns/genericode/1.0/" xmlns="">
  <Identification>
    <ShortName>{basename}</ShortName>
    <Version>{version}</Version>
    <CanonicalUri>urn:cef.eu:names:identifier:{basename}</CanonicalUri>
    <CanonicalVersionUri>urn:cef.eu:names:identifier:{basename}-{version}</CanonicalVersionUri>
  </Identification>
  <ColumnSet>
{column_xml}
  </ColumnSet>
  <SimpleCodeList>
{rows_xml}
  </SimpleCodeList>
</gc:CodeList>"""
    path = directory / f"{basename}.gc"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def codelist_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_gc(tmp_path, "Country", rows=[{"Code": "FR", "Name": "France"}])
    _write_gc(tmp_path, "Currency", rows=[{"Code": "EUR", "Name": "Euro"}])
    _write_gc(tmp_path, "ICD", rows=[{"Code": "0208", "Name": "BE:EN"}])
    _write_gc(tmp_path, "1001", rows=[{"Code": "380", "Name": "Commercial invoice"}])
    _write_gc(tmp_path, "1153", rows=[{"Code": "AAK", "Name": "Order number"}])
    _write_gc(
        tmp_path,
        "Payment",
        columns=["Code", "Name", "Remark"],
        rows=[{"Code": "30", "Name": "Credit transfer", "Remark": ""}],
    )
    _write_gc(
        tmp_path,
        "5305",
        columns=["Code", "Name", "Remark"],
        rows=[{"Code": "S", "Name": "Standard rate", "Remark": ""}],
    )
    _write_gc(tmp_path, "Allowance", rows=[{"Code": "41", "Name": "Bonus"}])
    _write_gc(tmp_path, "Item", rows=[{"Code": "AA", "Name": "Product version number"}])
    _write_gc(tmp_path, "Charge", rows=[{"Code": "AA", "Name": "Advertising"}])
    _write_gc(tmp_path, "MIME", columns=["Code"], rows=[{"Code": "application/pdf"}])
    _write_gc(tmp_path, "EAS", rows=[{"Code": "0088", "Name": "GLN"}])
    _write_gc(
        tmp_path,
        "VATEX",
        columns=["Code", "Name", "Remark"],
        rows=[{"Code": "VATEX-EU-79-C", "Name": "Exempt", "Remark": ""}],
    )
    monkeypatch.setenv("EINVOICING_EN16931_CODELIST_DIR", str(tmp_path))
    return tmp_path


class TestUnconfigured:
    def test_load_codelist_raises_when_env_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EINVOICING_EN16931_CODELIST_DIR", raising=False)
        with pytest.raises(codelists.CodelistNotConfiguredError):
            codelists.load_codelist("country")

    def test_check_country_code_raises_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("EINVOICING_EN16931_CODELIST_DIR", raising=False)
        with pytest.raises(codelists.CodelistNotConfiguredError):
            codelists.check_country_code("FR")

    def test_get_version_reports_errors_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EINVOICING_EN16931_CODELIST_DIR", raising=False)
        result = codelists.get_en16931_codelist_version()
        assert result["versions"] == {}
        assert len(result["errors"]) == 13


class TestConfigured:
    def test_check_country_code_found(self, codelist_dir: Path) -> None:
        result = codelists.check_country_code("FR")
        assert result == {"found": True, "Code": "FR", "Name": "France"}

    def test_check_country_code_not_found(self, codelist_dir: Path) -> None:
        result = codelists.check_country_code("ZZ")
        assert result == {"found": False, "Code": "ZZ"}

    def test_check_currency_code(self, codelist_dir: Path) -> None:
        assert codelists.check_currency_code("EUR")["found"] is True

    def test_check_icd_code(self, codelist_dir: Path) -> None:
        assert codelists.check_icd_code("0208")["found"] is True

    def test_check_document_name_code(self, codelist_dir: Path) -> None:
        assert codelists.check_document_name_code("380")["found"] is True

    def test_check_reference_qualifier_code(self, codelist_dir: Path) -> None:
        assert codelists.check_reference_qualifier_code("AAK")["found"] is True

    def test_check_payment_means_code(self, codelist_dir: Path) -> None:
        assert codelists.check_payment_means_code("30")["found"] is True

    def test_check_vat_category_code(self, codelist_dir: Path) -> None:
        assert codelists.check_vat_category_code("S")["found"] is True

    def test_check_allowance_reason_code(self, codelist_dir: Path) -> None:
        assert codelists.check_allowance_reason_code("41")["found"] is True

    def test_check_item_type_code(self, codelist_dir: Path) -> None:
        assert codelists.check_item_type_code("AA")["found"] is True

    def test_check_charge_reason_code(self, codelist_dir: Path) -> None:
        assert codelists.check_charge_reason_code("AA")["found"] is True

    def test_check_mime_code(self, codelist_dir: Path) -> None:
        assert codelists.check_mime_code("application/pdf")["found"] is True

    def test_check_eas_code(self, codelist_dir: Path) -> None:
        assert codelists.check_eas_code("0088")["found"] is True

    def test_check_vatex_code(self, codelist_dir: Path) -> None:
        assert codelists.check_vatex_code("VATEX-EU-79-C")["found"] is True

    def test_list_country_codes(self, codelist_dir: Path) -> None:
        rows = codelists.list_country_codes()
        assert rows == [{"Code": "FR", "Name": "France"}]

    def test_get_version_reports_versions(self, codelist_dir: Path) -> None:
        result = codelists.get_en16931_codelist_version()
        assert result["versions"]["country"] == "2026-05-15"
        assert result["errors"] == {}

    def test_missing_single_file_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EINVOICING_EN16931_CODELIST_DIR", str(tmp_path))
        with pytest.raises(codelists.CodelistNotConfiguredError):
            codelists.load_codelist("country")


class _FakeMCP:
    """Minimal stand-in for a FastMCP instance's .tool() decorator API."""

    def __init__(self) -> None:
        self.registered: dict[str, object] = {}

    def tool(self):
        def decorator(fn):
            self.registered[fn.__name__] = fn
            return fn

        return decorator


class TestRegisterEn16931CodelistTools:
    def test_registers_expected_tool_set(self) -> None:
        mcp = _FakeMCP()
        register_en16931_codelist_tools(mcp)
        assert set(mcp.registered) == {
            "list_country_codes",
            "check_country_code",
            "list_currency_codes",
            "check_currency_code",
            "list_icd_codes",
            "check_icd_code",
            "list_document_name_codes",
            "check_document_name_code",
            "list_reference_qualifier_codes",
            "check_reference_qualifier_code",
            "list_payment_means_codes",
            "check_payment_means_code",
            "list_vat_category_codes",
            "check_vat_category_code",
            "list_allowance_reason_codes",
            "check_allowance_reason_code",
            "list_item_type_codes",
            "check_item_type_code",
            "list_charge_reason_codes",
            "check_charge_reason_code",
            "list_mime_codes",
            "check_mime_code",
            "list_eas_codes",
            "check_eas_code",
            "list_vatex_codes",
            "check_vatex_code",
            "get_en16931_codelist_version",
        }

    def test_check_tool_reports_unconfigured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EINVOICING_EN16931_CODELIST_DIR", raising=False)
        mcp = _FakeMCP()
        register_en16931_codelist_tools(mcp)
        result = mcp.registered["check_country_code"]("FR")
        assert result["configured"] is False
        assert result["found"] is False

    def test_check_tool_reports_configured(self, codelist_dir: Path) -> None:
        mcp = _FakeMCP()
        register_en16931_codelist_tools(mcp)
        result = mcp.registered["check_country_code"]("FR")
        assert result["configured"] is True
        assert result["found"] is True
        assert result["Name"] == "France"
