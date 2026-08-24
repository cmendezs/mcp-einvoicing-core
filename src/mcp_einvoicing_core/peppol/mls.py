"""Peppol Message Level Status (MLS) — CORE-PEPPOL-MLR-1.

Models and Schematron validation for the MLS message a C3 responder sends
back to C2 to report delivery/validation outcome, per the vendored "Peppol
Message Level Status / Peppol MLS Specification" v1.1.0
(``specs/peppol/mls/Peppol Message Level Status _ Peppol MLS Specification.pdf``).

The MLS message syntax is a subset of UBL ``ApplicationResponse-2`` — there
is no bespoke MLS XSD, so **full UBL XSD validation is out of scope** here
(the UBL 2.1 schema set is not vendored in this package); the MLS
Schematron (``peppol-mls-1.0.1.sch``, compiled ``.xslt``, Apache-2.0
confirmed 2026-08-22) is the compliance check, bundled under
``resources/mls/``. Structure confirmed against the vendored
``specs/peppol/mls/example/MessageLevelStatus_Example_*.xml`` fixtures.

An MLS response is correlated to the original message via the SBDH
``MLS_TO``/``MLS_TYPE`` ``BusinessScope`` entries the sender may have set on
the original SBDH (see
``mcp_einvoicing_core.peppol.transport.models.StandardBusinessDocumentHeader.mls_to``/
``.mls_type``) and is exchanged C2↔C3 over AS4 like any other business
message (see ``mcp_einvoicing_core.peppol.transport.inbound``/``.client``).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from mcp_einvoicing_core.genericode import CodeList, parse_genericode
from mcp_einvoicing_core.schematron import (
    BaseStructuredValidator,
    ValidationResult,
    load_schematron_validator,
)
from mcp_einvoicing_core.xml_utils import safe_fromstring

_RESOURCES_DIR = Path(__file__).parent.parent / "resources" / "mls"
_MLS_SCHEMATRON = _RESOURCES_DIR / "schematron" / "peppol-mls-1.0.1.xslt"
_MLS_CODELIST_DIR = _RESOURCES_DIR / "codelist"

_UBL_AR_NS = "urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
_CAC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
_CBC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

MLS_CUSTOMIZATION_ID = "urn:peppol:edec:mls:1.0"
MLS_PROFILE_ID = "urn:peppol:edec:mls"

# Response codes (bundled codelist/ResponseCode.gc has the full set; these
# are the values shown across the vendored examples).
RESPONSE_CODE_ACKNOWLEDGED = "AB"  # Acknowledged
RESPONSE_CODE_ACCEPTED = "AP"  # Accepted
RESPONSE_CODE_REJECTED = "RE"  # Rejected

# StatusReasonCode values (peppol-mls-1.0.1.sch): syntax violation, rule
# violation fatal, rule violation warning, failure of delivery.
STATUS_REASON_SYNTAX_VIOLATION = "SV"
STATUS_REASON_RULE_VIOLATION_FATAL = "BV"
STATUS_REASON_RULE_VIOLATION_WARNING = "BW"
STATUS_REASON_FAILURE_OF_DELIVERY = "FD"


class MLSEndpoint(BaseModel):
    """``<SenderParty>``/``<ReceiverParty>``: a Peppol participant endpoint."""

    scheme_id: str
    value: str


class MLSStatus(BaseModel):
    """``<cac:Status><cbc:StatusReasonCode>``: machine-readable failure category."""

    reason_code: str


class MLSResponse(BaseModel):
    """A single ``<cac:Response>`` — at the document level or line level."""

    response_code: str | None = None
    description: str | None = None
    status: MLSStatus | None = None


class MLSLineReference(BaseModel):
    """``<cac:LineReference><cbc:LineID>``: identifies the line a LineResponse
    covers, or the literal ``"NA"`` when not applicable."""

    line_id: str


class MLSLineResponse(BaseModel):
    """A single ``<cac:LineResponse>``: one or more Responses for one line."""

    line_reference: MLSLineReference
    responses: list[MLSResponse] = Field(default_factory=list)


class MLSDocumentReference(BaseModel):
    """``<cac:DocumentReference><cbc:ID>``: the SBDH ``InstanceIdentifier``
    of the source message this MLS reports on."""

    id: str


class MLSDocumentResponse(BaseModel):
    """``<cac:DocumentResponse>``: the overall response plus any per-line detail."""

    response: MLSResponse
    document_reference: MLSDocumentReference
    line_responses: list[MLSLineResponse] = Field(default_factory=list)


class MessageLevelStatus(BaseModel):
    """A parsed MLS document (UBL ``ApplicationResponse-2`` subset)."""

    customization_id: str
    profile_id: str
    id: str
    issue_date: str
    issue_time: str | None = None
    sender: MLSEndpoint
    receiver: MLSEndpoint
    document_response: MLSDocumentResponse


def _local(tag: object) -> str | None:
    if not isinstance(tag, str):
        return None
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find(parent, local_name: str):
    for el in parent:
        if _local(el.tag) == local_name:
            return el
    return None


def _text(parent, local_name: str) -> str | None:
    el = _find(parent, local_name)
    return (el.text or "").strip() if el is not None else None


def _parse_endpoint(party_el) -> MLSEndpoint:
    endpoint_el = _find(party_el, "EndpointID")
    return MLSEndpoint(
        scheme_id=endpoint_el.get("schemeID", ""), value=(endpoint_el.text or "").strip()
    )


def _parse_response(response_el) -> MLSResponse:
    status_el = _find(response_el, "Status")
    status = None
    if status_el is not None:
        reason_code = _text(status_el, "StatusReasonCode")
        if reason_code:
            status = MLSStatus(reason_code=reason_code)
    return MLSResponse(
        response_code=_text(response_el, "ResponseCode"),
        description=_text(response_el, "Description"),
        status=status,
    )


def parse_mls(xml_bytes: bytes) -> MessageLevelStatus:
    """Parse an MLS (UBL ApplicationResponse-2 subset) document.

    Raises:
        etree.XMLSyntaxError: On malformed XML.
        AttributeError: If required elements are missing — run `validate_mls`
            first if the input is untrusted.
    """
    root = safe_fromstring(xml_bytes)

    sender = _parse_endpoint(_find(root, "SenderParty"))
    receiver = _parse_endpoint(_find(root, "ReceiverParty"))

    doc_response_el = _find(root, "DocumentResponse")
    response = _parse_response(_find(doc_response_el, "Response"))
    doc_ref_el = _find(doc_response_el, "DocumentReference")
    doc_ref = MLSDocumentReference(id=_text(doc_ref_el, "ID") or "")

    line_responses = []
    for line_response_el in doc_response_el:
        if _local(line_response_el.tag) != "LineResponse":
            continue
        line_ref_el = _find(line_response_el, "LineReference")
        line_ref = MLSLineReference(line_id=_text(line_ref_el, "LineID") or "")
        responses = [
            _parse_response(r_el)
            for r_el in line_response_el
            if _local(r_el.tag) == "Response"
        ]
        line_responses.append(MLSLineResponse(line_reference=line_ref, responses=responses))

    document_response = MLSDocumentResponse(
        response=response, document_reference=doc_ref, line_responses=line_responses
    )

    return MessageLevelStatus(
        customization_id=_text(root, "CustomizationID") or "",
        profile_id=_text(root, "ProfileID") or "",
        id=_text(root, "ID") or "",
        issue_date=_text(root, "IssueDate") or "",
        issue_time=_text(root, "IssueTime"),
        sender=sender,
        receiver=receiver,
        document_response=document_response,
    )


def validate_mls(xml_bytes: bytes) -> ValidationResult:
    """Validate an MLS document against the bundled MLS Schematron.

    XSD validation is out of scope (see module docstring — no bespoke MLS
    XSD exists; full UBL 2.1 XSD validation is not implemented here).
    Requires the ``[xslt2]`` optional extra (the stylesheet is XSLT 2.0).
    """
    validator = load_schematron_validator(_MLS_SCHEMATRON)
    return validator.validate(xml_bytes, profile="mls", syntax="UBL")


def mls_schematron_validator() -> BaseStructuredValidator:
    """Return the bundled MLS Schematron validator directly (no XSD step)."""
    return load_schematron_validator(_MLS_SCHEMATRON)


_MLS_CODELISTS = {
    "response_code": "ResponseCode",
    "status_reason_code": "StatusReasonCode",
}


def load_mls_codelist(name: str) -> CodeList:
    """Load a bundled MLS genericode list: "response_code" or "status_reason_code"."""
    return parse_genericode((_MLS_CODELIST_DIR / f"{_MLS_CODELISTS[name]}.gc").read_bytes())


def build_mls(
    *,
    mls_id: str,
    issue_date: str,
    sender: MLSEndpoint,
    receiver: MLSEndpoint,
    document_response: MLSDocumentResponse,
    issue_time: str | None = None,
) -> bytes:
    """Build a UBL ``ApplicationResponse-2`` MLS document.

    For C3 responders replying to a message that requested an MLS (see
    ``StandardBusinessDocumentHeader.mls_to``/``.mls_type``). Does not sign
    or transmit — pass the returned bytes as the payload to
    ``AS4TransportClient.send()``/`peppol.transport.AS4MessageEnvelope`.

    Args:
        mls_id: The ``cbc:ID`` of this MLS document.
        issue_date: ISO date string, e.g. "2026-08-23".
        sender: This Access Point's endpoint (the MLS sender = original
            message's C3/receiver).
        receiver: The endpoint to send this MLS to (normally the original
            message's SBDH ``MLS_TO`` value).
        document_response: The response content — build with
            `MLSDocumentResponse` directly for full control.
        issue_time: ISO time string, e.g. "12:00:00Z".
    """
    from lxml import etree  # noqa: PLC0415

    nsmap = {None: _UBL_AR_NS, "cac": _CAC_NS, "cbc": _CBC_NS}
    root = etree.Element(f"{{{_UBL_AR_NS}}}ApplicationResponse", nsmap=nsmap)

    etree.SubElement(root, f"{{{_CBC_NS}}}CustomizationID").text = MLS_CUSTOMIZATION_ID
    etree.SubElement(root, f"{{{_CBC_NS}}}ProfileID").text = MLS_PROFILE_ID
    etree.SubElement(root, f"{{{_CBC_NS}}}ID").text = mls_id
    etree.SubElement(root, f"{{{_CBC_NS}}}IssueDate").text = issue_date
    if issue_time:
        etree.SubElement(root, f"{{{_CBC_NS}}}IssueTime").text = issue_time

    sender_party = etree.SubElement(root, f"{{{_CAC_NS}}}SenderParty")
    sender_endpoint = etree.SubElement(sender_party, f"{{{_CBC_NS}}}EndpointID")
    sender_endpoint.set("schemeID", sender.scheme_id)
    sender_endpoint.text = sender.value

    receiver_party = etree.SubElement(root, f"{{{_CAC_NS}}}ReceiverParty")
    receiver_endpoint = etree.SubElement(receiver_party, f"{{{_CBC_NS}}}EndpointID")
    receiver_endpoint.set("schemeID", receiver.scheme_id)
    receiver_endpoint.text = receiver.value

    doc_response_el = etree.SubElement(root, f"{{{_CAC_NS}}}DocumentResponse")
    _append_response(doc_response_el, document_response.response)

    doc_ref_el = etree.SubElement(doc_response_el, f"{{{_CAC_NS}}}DocumentReference")
    etree.SubElement(doc_ref_el, f"{{{_CBC_NS}}}ID").text = document_response.document_reference.id

    for line_response in document_response.line_responses:
        line_response_el = etree.SubElement(doc_response_el, f"{{{_CAC_NS}}}LineResponse")
        line_ref_el = etree.SubElement(line_response_el, f"{{{_CAC_NS}}}LineReference")
        etree.SubElement(line_ref_el, f"{{{_CBC_NS}}}LineID").text = line_response.line_reference.line_id
        for response in line_response.responses:
            _append_response(line_response_el, response)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def _append_response(parent, response: MLSResponse) -> None:
    from lxml import etree  # noqa: PLC0415

    response_el = etree.SubElement(parent, f"{{{_CAC_NS}}}Response")
    if response.response_code:
        etree.SubElement(response_el, f"{{{_CBC_NS}}}ResponseCode").text = response.response_code
    if response.description:
        etree.SubElement(response_el, f"{{{_CBC_NS}}}Description").text = response.description
    if response.status:
        status_el = etree.SubElement(response_el, f"{{{_CAC_NS}}}Status")
        etree.SubElement(status_el, f"{{{_CBC_NS}}}StatusReasonCode").text = response.status.reason_code
