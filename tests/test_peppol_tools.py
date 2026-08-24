"""Tests for the shared Peppol tool plugin (CORE-PEPPOL-TOOLS-1).

asyncio_mode = "auto" (pyproject.toml), no @pytest.mark.asyncio needed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from mcp_einvoicing_core.peppol.tools import (
    default_id_adapter,
    register_peppol_tools,
)


class _FakeMCP:
    """Minimal stand-in for a FastMCP instance's .tool() decorator API."""

    def __init__(self) -> None:
        self.registered: dict[str, Callable[..., Any]] = {}

    def tool(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.registered[fn.__name__] = fn
            return fn

        return decorator


_SERVICE_GROUP_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<smp:ServiceGroup xmlns:smp="http://busdox.org/serviceMetadata/publishing/1.0/">
  <smp:ServiceMetadataReferenceCollection>
    <smp:ServiceMetadataReference
        href="https://test.smp.acube.io/iso6523-actorid-upis%3A%3A0208%3A0123456789/services/urn%3Aoasis%3Anames%3Aspecification%3Aubl%3Aschema%3Axsd%3AInvoice-2%3A%3AInvoice%23%23urn%3Acen.eu%3Aen16931%3A2017%23compliant%23urn%3Afdc%3Apeppol.eu%3A2017%3Apoacc%3Abilling%3A3.0%3A%3A2.1"/>
  </smp:ServiceMetadataReferenceCollection>
</smp:ServiceGroup>"""


def _doh_json(hostname: str = "test.smp.acube.io") -> dict:
    naptr_data = f'100 0 "U" "Meta:SMP" "!^.*$!https://{hostname}!" .'
    return {"Status": 0, "Answer": [{"type": 35, "data": naptr_data}]}


class TestDefaultIdAdapter:
    def test_passes_through_scheme_qualified_identifier(self) -> None:
        assert default_id_adapter("0208:0123456789") == "0208:0123456789"

    def test_rejects_bare_number(self) -> None:
        with pytest.raises(ValueError):
            default_id_adapter("0123456789")


class TestRegisterPeppolTools:
    def test_registers_expected_tool_set(self) -> None:
        mcp = _FakeMCP()
        register_peppol_tools(mcp)
        assert set(mcp.registered) == {
            "peppol_lookup_participant",
            "peppol_get_service_endpoint",
            "resolve_peppol_dns",
            "peppol_send",
            "list_participant_id_schemes",
            "list_document_type_ids",
            "list_process_ids",
            "list_spis_use_case_ids",
            "check_document_type_id_in_codelist",
            "check_process_id_in_codelist",
            "check_participant_id_scheme_in_codelist",
            "get_peppol_codelist_version",
            "peppol_directory_search",
        }

    async def test_lookup_uses_default_adapter_and_rejects_bare_identifier(self) -> None:
        mcp = _FakeMCP()
        register_peppol_tools(mcp)
        result = await mcp.registered["peppol_lookup_participant"]("0123456789")
        assert result["is_registered"] is False
        assert "error" in result

    async def test_lookup_uses_supplied_adapter_end_to_end(self, httpx_mock) -> None:
        mcp = _FakeMCP()

        def be_adapter(identifier: str) -> str:
            if ":" in identifier:
                return identifier
            return f"0208:{identifier}"

        register_peppol_tools(mcp, id_adapter=be_adapter)

        httpx_mock.add_response(json=_doh_json("test.smp.acube.io"))  # DNS (SML) step
        httpx_mock.add_response(content=_SERVICE_GROUP_XML)  # SMP service group step

        result = await mcp.registered["peppol_lookup_participant"]("0123456789")
        assert result["is_registered"] is True
        assert result["participant_id"] == "0208:0123456789"
        assert result["smp_hostname"] == "test.smp.acube.io"
        assert result["supported_document_types"]

    async def test_resolve_peppol_dns_reports_registration(self, httpx_mock) -> None:
        mcp = _FakeMCP()
        register_peppol_tools(mcp)
        httpx_mock.add_response(json=_doh_json("test.smp.acube.io"))
        result = await mcp.registered["resolve_peppol_dns"]("0208:0123456789")
        assert result["is_registered"] is True
        assert result["smp_hostname"] == "test.smp.acube.io"

    async def test_resolve_peppol_dns_rejects_bare_identifier_without_adapter(self) -> None:
        mcp = _FakeMCP()
        register_peppol_tools(mcp)
        result = await mcp.registered["resolve_peppol_dns"]("0123456789")
        assert result["smp_hostname"] is None
        assert "error" in result

    async def test_peppol_send_rejects_invalid_recipient(self) -> None:
        mcp = _FakeMCP()
        register_peppol_tools(mcp)
        result = await mcp.registered["peppol_send"](
            invoice_xml_base64="PGE+PC9hPg==",
            recipient_identifier="not-a-valid-id",
            sender_id="POP000001",
            certificate_path="/nonexistent/cert.pem",
            private_key_path="/nonexistent/key.pem",
        )
        assert result["status"] == "error"

    async def test_peppol_send_rejects_invalid_base64(self) -> None:
        mcp = _FakeMCP()
        register_peppol_tools(mcp)
        result = await mcp.registered["peppol_send"](
            invoice_xml_base64="not valid base64!!",
            recipient_identifier="0208:0123456789",
            sender_id="POP000001",
            certificate_path="/nonexistent/cert.pem",
            private_key_path="/nonexistent/key.pem",
        )
        assert result["status"] == "error"


class TestCodelistToolsUnconfigured:
    """Without EINVOICING_PEPPOL_CODELIST_DIR, every codelist tool must
    return a clear configured=False result rather than raising."""

    def test_list_and_check_tools_report_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EINVOICING_PEPPOL_CODELIST_DIR", raising=False)
        mcp = _FakeMCP()
        register_peppol_tools(mcp)

        assert mcp.registered["list_participant_id_schemes"]()["configured"] is False
        assert mcp.registered["list_document_type_ids"]()["configured"] is False
        assert mcp.registered["list_process_ids"]()["configured"] is False
        assert mcp.registered["list_spis_use_case_ids"]()["configured"] is False
        assert mcp.registered["check_document_type_id_in_codelist"]("s", "v")["configured"] is False
        assert mcp.registered["check_process_id_in_codelist"]("s", "v")["configured"] is False
        assert mcp.registered["check_participant_id_scheme_in_codelist"]("0208")["configured"] is False

    def test_get_version_reports_all_errors_when_unconfigured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EINVOICING_PEPPOL_CODELIST_DIR", raising=False)
        mcp = _FakeMCP()
        register_peppol_tools(mcp)
        result = mcp.registered["get_peppol_codelist_version"]()
        assert result["versions"] == {}
        assert len(result["errors"]) == 5


class TestCodelistToolsConfigured:
    def test_list_participant_id_schemes_returns_data(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        (tmp_path / "Participant-identifier-schemes-v9.7.gc").write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<gc:CodeList xmlns:gc="http://docs.oasis-open.org/codelist/ns/genericode/1.0/">
  <Identification><ShortName>x</ShortName><Version>9.7</Version></Identification>
  <ColumnSet>
    <Column Id="schemeid" Use="required"><ShortName>s</ShortName><Data Type="string" /></Column>
    <Column Id="iso6523" Use="required"><ShortName>i</ShortName><Data Type="string" /></Column>
    <Column Id="state" Use="required"><ShortName>st</ShortName><Data Type="string" /></Column>
  </ColumnSet>
  <SimpleCodeList>
    <Row>
      <Value ColumnRef="schemeid"><SimpleValue>BE:EN</SimpleValue></Value>
      <Value ColumnRef="iso6523"><SimpleValue>0208</SimpleValue></Value>
      <Value ColumnRef="state"><SimpleValue>active</SimpleValue></Value>
    </Row>
  </SimpleCodeList>
</gc:CodeList>""",
            encoding="utf-8",
        )
        monkeypatch.setenv("EINVOICING_PEPPOL_CODELIST_DIR", str(tmp_path))
        mcp = _FakeMCP()
        register_peppol_tools(mcp)

        result = mcp.registered["list_participant_id_schemes"]()
        assert result["configured"] is True
        assert result["schemes"][0]["iso6523"] == "0208"

        check = mcp.registered["check_participant_id_scheme_in_codelist"]("0208")
        assert check["configured"] is True
        assert check["found"] is True


class TestPeppolDirectorySearchTool:
    async def test_requires_a_query_term(self) -> None:
        mcp = _FakeMCP()
        register_peppol_tools(mcp)
        result = await mcp.registered["peppol_directory_search"]()
        assert "error" in result
        assert result["matches"] == []

    async def test_searches_and_returns_matches(self, httpx_mock) -> None:
        httpx_mock.add_response(
            json={
                "version": "1.0",
                "total-result-count": 1,
                "used-result-count": 1,
                "result-page-index": 0,
                "result-page-count": 20,
                "first-result-index": 0,
                "last-result-index": 0,
                "query-terms": "q=acme",
                "creation-dt": "2026-08-23T00:00:00Z",
                "matches": [
                    {
                        "participantID": {"scheme": "iso6523-actorid-upis", "value": "0208:1"},
                        "docTypes": [],
                        "entities": [{"name": [{"name": "Acme"}], "countryCode": "BE"}],
                    }
                ],
            }
        )
        mcp = _FakeMCP()
        register_peppol_tools(mcp)
        result = await mcp.registered["peppol_directory_search"](q="acme")
        assert result["total_result_count"] == 1
        assert result["matches"][0]["entities"][0]["names"][0]["name"] == "Acme"
