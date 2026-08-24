"""Tests for Peppol MLS (Message Level Status) — CORE-PEPPOL-MLR-1.

Uses the vendored ``specs/peppol/mls/example/MessageLevelStatus_Example_*.xml``
fixtures directly, per the plan's verification step 8. Requires the
``[xslt2]`` optional extra (``saxonche``) — the bundled Schematron
stylesheet is XSLT 2.0.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from mcp_einvoicing_core.peppol.mls import (
    MLSDocumentReference,
    MLSDocumentResponse,
    MLSEndpoint,
    MLSResponse,
    MLSStatus,
    build_mls,
    load_mls_codelist,
    mls_schematron_validator,
    parse_mls,
    validate_mls,
)
from mcp_einvoicing_core.peppol.mls_tools import register_peppol_mls_tools
from mcp_einvoicing_core.peppol.transport.models import (
    SBDHScope,
    StandardBusinessDocumentHeader,
)

_EXAMPLES_DIR = Path(__file__).parent.parent / "specs" / "peppol" / "mls" / "example"
_HAS_EXAMPLES = _EXAMPLES_DIR.is_dir()
requires_examples = pytest.mark.skipif(
    not _HAS_EXAMPLES, reason="vendored specs/peppol/mls example fixtures not present"
)

pytest.importorskip("saxonche", reason="Schematron validation requires the [xslt2] extra")

_ALL_EXAMPLES = [
    "MessageLevelStatus_Example_AB.xml",
    "MessageLevelStatus_Example_AB2.xml",
    "MessageLevelStatus_Example_AB3.xml",
    "MessageLevelStatus_Example_AP.xml",
    "MessageLevelStatus_Example_RE.xml",
    "MessageLevelStatus_Example_RE2.xml",
    "MessageLevelStatus_Example_RE3.xml",
    "MessageLevelStatus_Example_RE4.xml",
]


@pytest.fixture()
def ab_xml() -> bytes:
    return (_EXAMPLES_DIR / "MessageLevelStatus_Example_AB.xml").read_bytes()


@pytest.fixture()
def re2_xml() -> bytes:
    return (_EXAMPLES_DIR / "MessageLevelStatus_Example_RE2.xml").read_bytes()


@requires_examples
class TestParseMls:
    def test_parses_acknowledged_response(self, ab_xml: bytes) -> None:
        mls = parse_mls(ab_xml)
        assert mls.customization_id == "urn:peppol:edec:mls:1.0"
        assert mls.profile_id == "urn:peppol:edec:mls"
        assert mls.id == "MLS-ID123"
        assert mls.sender.scheme_id == "0242"
        assert mls.sender.value == "123456"
        assert mls.receiver.value == "234567"
        assert mls.document_response.response.response_code == "AB"
        assert (
            mls.document_response.document_reference.id
            == "90f14eff-3705-4869-ad3c-caae270a234e"
        )
        assert mls.document_response.line_responses == []

    def test_parses_rejected_response_with_line_details(self, re2_xml: bytes) -> None:
        mls = parse_mls(re2_xml)
        assert mls.document_response.response.response_code == "RE"
        assert mls.document_response.response.description == "Rejected due to validation errors"

        line_responses = mls.document_response.line_responses
        assert len(line_responses) == 1
        line = line_responses[0]
        assert "CatalogueLine[3]" in line.line_reference.line_id
        assert len(line.responses) == 2
        assert line.responses[0].status.reason_code == "BV"
        assert line.responses[1].status.reason_code == "BW"


@requires_examples
class TestValidateMls:
    @pytest.mark.parametrize("filename", _ALL_EXAMPLES)
    def test_vendored_examples_pass(self, filename: str) -> None:
        xml_bytes = (_EXAMPLES_DIR / filename).read_bytes()
        result = validate_mls(xml_bytes)
        assert result.is_valid, result.errors

    def test_negative_response_without_line_failure_fails(self) -> None:
        # SCH-MLS-23/24: a "RE" (rejected) MLS MUST contain at least one
        # LineResponse with a failure-level Status — a document-level
        # Status alone does not satisfy the rule.
        doc_response = MLSDocumentResponse(
            response=MLSResponse(response_code="RE", description="Rejected"),
            document_reference=MLSDocumentReference(id="doc-ref-1"),
        )
        xml_bytes = build_mls(
            mls_id="MLS-NEG-1",
            issue_date="2026-08-23",
            issue_time="12:00:00Z",
            sender=MLSEndpoint(scheme_id="0242", value="123456"),
            receiver=MLSEndpoint(scheme_id="0242", value="234567"),
            document_response=doc_response,
        )
        result = validate_mls(xml_bytes)
        assert result.is_valid is False
        assert any(e.rule_id == "SCH-MLS-24" for e in result.errors)

    def test_missing_issue_time_fails(self) -> None:
        # SCH-MLS-05: IssueTime is always required, not just for negative MLS.
        doc_response = MLSDocumentResponse(
            response=MLSResponse(response_code="AB"),
            document_reference=MLSDocumentReference(id="doc-ref-1"),
        )
        xml_bytes = build_mls(
            mls_id="MLS-NO-TIME",
            issue_date="2026-08-23",
            sender=MLSEndpoint(scheme_id="0242", value="123456"),
            receiver=MLSEndpoint(scheme_id="0242", value="234567"),
            document_response=doc_response,
        )
        result = validate_mls(xml_bytes)
        assert result.is_valid is False
        assert any(e.rule_id == "SCH-MLS-05" for e in result.errors)


class TestMlsSchematronValidatorFactory:
    def test_returns_working_validator(self, ab_xml: bytes) -> None:
        validator = mls_schematron_validator()
        result = validator.validate(ab_xml)
        assert result.is_valid


class TestBuildMls:
    def test_build_document_level_response_is_valid(self) -> None:
        doc_response = MLSDocumentResponse(
            response=MLSResponse(response_code="AB"),
            document_reference=MLSDocumentReference(id="90f14eff-3705-4869-ad3c-caae270a234e"),
        )
        xml_bytes = build_mls(
            mls_id="MLS-TEST-1",
            issue_date="2026-08-23",
            issue_time="12:00:00Z",
            sender=MLSEndpoint(scheme_id="0242", value="123456"),
            receiver=MLSEndpoint(scheme_id="0242", value="234567"),
            document_response=doc_response,
        )
        result = validate_mls(xml_bytes)
        assert result.is_valid, result.errors

    def test_build_rejected_response_with_line_failure_is_valid(self) -> None:
        # SCH-MLS-23/24 require a negative ("RE") MLS to carry at least one
        # LineResponse with a failure-level Status (BV or FD) — a
        # document-level Status alone is not sufficient.
        from mcp_einvoicing_core.peppol.mls import MLSLineReference, MLSLineResponse

        doc_response = MLSDocumentResponse(
            response=MLSResponse(response_code="RE", description="Rejected"),
            document_reference=MLSDocumentReference(id="90f14eff-3705-4869-ad3c-caae270a234e"),
            line_responses=[
                MLSLineResponse(
                    line_reference=MLSLineReference(line_id="NA"),
                    responses=[
                        MLSResponse(
                            description="Validation error",
                            status=MLSStatus(reason_code="BV"),
                        )
                    ],
                )
            ],
        )
        xml_bytes = build_mls(
            mls_id="MLS-TEST-2",
            issue_date="2026-08-23",
            issue_time="12:00:00Z",
            sender=MLSEndpoint(scheme_id="0242", value="123456"),
            receiver=MLSEndpoint(scheme_id="0242", value="234567"),
            document_response=doc_response,
        )
        result = validate_mls(xml_bytes)
        assert result.is_valid, result.errors

    def test_build_and_reparse_round_trips(self) -> None:
        doc_response = MLSDocumentResponse(
            response=MLSResponse(response_code="AP"),
            document_reference=MLSDocumentReference(id="doc-ref-1"),
        )
        xml_bytes = build_mls(
            mls_id="MLS-TEST-3",
            issue_date="2026-08-23",
            issue_time="12:00:00Z",
            sender=MLSEndpoint(scheme_id="0242", value="111"),
            receiver=MLSEndpoint(scheme_id="0242", value="222"),
            document_response=doc_response,
        )
        reparsed = parse_mls(xml_bytes)
        assert reparsed.id == "MLS-TEST-3"
        assert reparsed.document_response.response.response_code == "AP"


class TestBundledMlsCodelists:
    def test_load_response_code_codelist(self) -> None:
        codelist = load_mls_codelist("response_code")
        assert len(codelist.rows) > 0

    def test_load_status_reason_code_codelist(self) -> None:
        codelist = load_mls_codelist("status_reason_code")
        assert len(codelist.rows) > 0

    def test_unknown_codelist_raises(self) -> None:
        with pytest.raises(KeyError):
            load_mls_codelist("bogus")


class TestSbdhMlsTypeHelpers:
    def test_mls_to_and_mls_type_from_scope(self) -> None:
        sbdh = StandardBusinessDocumentHeader(
            business_scope=[
                SBDHScope(type="MLS_TO", instance_identifier="0242:987654", identifier="iso6523-actorid-upis"),
                SBDHScope(type="MLS_TYPE", instance_identifier="FAILURE_ONLY"),
            ]
        )
        assert sbdh.mls_to == "0242:987654"
        assert sbdh.mls_type == "FAILURE_ONLY"

    def test_none_when_absent(self) -> None:
        sbdh = StandardBusinessDocumentHeader()
        assert sbdh.mls_to is None
        assert sbdh.mls_type is None


class _FakeMCP:
    def __init__(self) -> None:
        self.registered: dict[str, object] = {}

    def tool(self):
        def decorator(fn):
            self.registered[fn.__name__] = fn
            return fn

        return decorator


@requires_examples
class TestRegisterPeppolMlsTools:
    def test_registers_expected_tool_set(self) -> None:
        mcp = _FakeMCP()
        register_peppol_mls_tools(mcp)
        assert set(mcp.registered) == {"validate_mls_message", "build_mls_message"}

    def test_validate_mls_message_tool(self, ab_xml: bytes) -> None:
        mcp = _FakeMCP()
        register_peppol_mls_tools(mcp)
        result = mcp.registered["validate_mls_message"](base64.b64encode(ab_xml).decode())
        assert result["is_valid"] is True

    def test_build_mls_message_tool(self) -> None:
        mcp = _FakeMCP()
        register_peppol_mls_tools(mcp)
        result = mcp.registered["build_mls_message"](
            mls_id="MLS-TOOL-1",
            issue_date="2026-08-23",
            sender_scheme_id="0242",
            sender_value="123456",
            receiver_scheme_id="0242",
            receiver_value="234567",
            document_reference_id="doc-ref-tool",
            response_code="AB",
            issue_time="12:00:00Z",
        )
        xml_bytes = base64.b64decode(result["mls_xml_base64"])
        validate_result = mcp.registered["validate_mls_message"](
            base64.b64encode(xml_bytes).decode()
        )
        assert validate_result["is_valid"] is True
