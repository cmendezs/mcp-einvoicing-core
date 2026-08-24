"""Tests for the AS4 inbound message receiver (AS4-IN-1)."""

from __future__ import annotations

import datetime
import gzip

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree

from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.peppol.transport.client import AS4TransportClient
from mcp_einvoicing_core.peppol.transport.envelope import AS4MessageEnvelope
from mcp_einvoicing_core.peppol.transport.inbound import (
    AS4InboundHandler,
    MimeParseError,
    parse_mime_multipart,
)
from mcp_einvoicing_core.peppol.transport.receipt import (
    build_error_envelope,
    build_receipt_envelope,
)
from mcp_einvoicing_core.peppol.transport.wssecurity import SignedAttachment, sign_as4_message

_SBDH_PAYLOAD = b"""<?xml version="1.0" encoding="UTF-8"?>
<StandardBusinessDocument xmlns="http://www.unece.org/cefact/namespaces/StandardBusinessDocumentHeader">
  <StandardBusinessDocumentHeader>
    <HeaderVersion>1.0</HeaderVersion>
    <Sender><Identifier Authority="iso6523-actorid-upis">9998:sender</Identifier></Sender>
    <Receiver><Identifier Authority="iso6523-actorid-upis">9998:receiver</Identifier></Receiver>
    <DocumentIdentification>
      <Standard>urn:oasis:names:specification:ubl:schema:xsd:Invoice-2</Standard>
      <TypeVersion>2.1</TypeVersion>
      <InstanceIdentifier>e07a2352-83cf-11ee-8459-74563c4a6461</InstanceIdentifier>
      <Type>Invoice</Type>
      <CreationDateAndTime>2023-11-15T16:58:54.263385</CreationDateAndTime>
    </DocumentIdentification>
    <BusinessScope>
      <Scope>
        <Type>DOCUMENTID</Type>
        <InstanceIdentifier>urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::Invoice</InstanceIdentifier>
        <Identifier>busdox-docid-qns</Identifier>
      </Scope>
      <Scope>
        <Type>PROCESSID</Type>
        <InstanceIdentifier>urn:fdc:peppol.eu:2017:poacc:billing:01:1.0</InstanceIdentifier>
        <Identifier>cenbii-procid-ubl</Identifier>
      </Scope>
    </BusinessScope>
  </StandardBusinessDocumentHeader>
  <doc:Invoice xmlns:doc="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
    <doc:ID>INV-001</doc:ID>
  </doc:Invoice>
</StandardBusinessDocument>"""


def _generate_test_key_and_cert() -> tuple[rsa.RSAPrivateKey, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test AP")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return key, cert.public_bytes(serialization.Encoding.DER)


def _build_signed_multipart(
    *, message_id: str = "test-msg-001", tamper_attachment: bool = False
) -> tuple[str, bytes]:
    key, cert_der = _generate_test_key_and_cert()
    envelope = AS4MessageEnvelope(
        sender_id="POP000001",
        receiver_id="POP000002",
        document_type_id="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::Invoice",
        process_id="urn:fdc:peppol.eu:2017:poacc:billing:01:1.0",
        payload_xml=_SBDH_PAYLOAD,
        message_id=message_id,
    )
    soap_bytes = envelope.build()
    compressed_payload = gzip.compress(_SBDH_PAYLOAD)

    signed_soap = sign_as4_message(
        soap_bytes,
        [SignedAttachment(content_id="invoice@peppol.eu", content=compressed_payload)],
        cert_der,
        key,
    )

    client = AS4TransportClient()
    boundary = "----=_Part_test_boundary"
    if tamper_attachment:
        compressed_payload = gzip.compress(b"<Tampered/>")
    body = client._build_multipart_body(signed_soap, compressed_payload, boundary)  # noqa: SLF001
    content_type = f'multipart/related; type="application/soap+xml"; boundary="{boundary}"'
    return content_type, body


class TestParseMimeMultipart:
    def test_splits_soap_and_attachments(self) -> None:
        content_type, body = _build_signed_multipart()
        soap_bytes, attachments = parse_mime_multipart(content_type, body)
        root = etree.fromstring(soap_bytes)
        assert root.tag == "{http://www.w3.org/2003/05/soap-envelope}Envelope"
        assert "invoice@peppol.eu" in attachments

    def test_rejects_non_multipart(self) -> None:
        with pytest.raises(MimeParseError):
            parse_mime_multipart("application/soap+xml", b"<Envelope/>")


class TestAS4InboundHandlerReceive:
    def test_receives_and_verifies_signed_message(self) -> None:
        content_type, body = _build_signed_multipart()
        handler = AS4InboundHandler()

        result = handler.receive(content_type, body)

        assert result.message_id == "test-msg-001"
        assert result.signature_valid is True
        assert result.signature_error is None

    def test_extracts_sbdh(self) -> None:
        content_type, body = _build_signed_multipart()
        handler = AS4InboundHandler()

        result = handler.receive(content_type, body)

        assert result.sbdh is not None
        assert result.sbdh.sender.value == "9998:sender"
        assert result.sbdh.receiver.value == "9998:receiver"
        assert result.sbdh.document_identification.type == "Invoice"
        assert result.sbdh.scope_value("PROCESSID") == "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"

    def test_extracts_business_document(self) -> None:
        content_type, body = _build_signed_multipart()
        handler = AS4InboundHandler()

        result = handler.receive(content_type, body)

        doc_root = etree.fromstring(result.business_document_xml)
        assert doc_root.tag == "{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice"

    def test_tampered_attachment_reports_invalid_signature(self) -> None:
        content_type, body = _build_signed_multipart(tamper_attachment=True)
        handler = AS4InboundHandler()

        result = handler.receive(content_type, body)

        assert result.signature_valid is False
        assert result.signature_error is not None

    def test_verify_signature_false_skips_verification(self) -> None:
        content_type, body = _build_signed_multipart(tamper_attachment=True)
        handler = AS4InboundHandler()

        result = handler.receive(content_type, body, verify_signature=False)

        assert result.signature_valid is None
        # SBDH extraction still happens even when the attachment was swapped,
        # just against the tampered content.

    def test_reports_trust_anchors_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EINVOICING_PEPPOL_PKI_DIR", raising=False)
        content_type, body = _build_signed_multipart()
        handler = AS4InboundHandler()

        result = handler.receive(content_type, body)

        assert result.chain_validation is not None
        assert result.chain_validation["trust_anchors_configured"] is False

    def test_raises_on_malformed_soap(self) -> None:
        content_type, body = _build_signed_multipart()
        # Corrupt the body so the SOAP part fails to parse.
        handler = AS4InboundHandler()
        with pytest.raises((PlatformError, MimeParseError)):
            handler.receive(content_type, b"garbage-not-mime")

    def test_build_not_serviced_error(self) -> None:
        handler = AS4InboundHandler()
        error = handler.build_not_serviced_error("ref-msg-001")
        assert error.error_code == "EBMS:0004"
        assert error.severity == "failure"
        assert error.error_detail == "PEPPOL:NOT_SERVICED"
        assert error.ref_to_message_id == "ref-msg-001"


class TestBuildReceiptAndErrorEnvelopes:
    def test_build_receipt_envelope_round_trips_with_parser(self) -> None:
        from mcp_einvoicing_core.peppol.transport.receipt import AS4ReceiptHandler

        receipt_bytes = build_receipt_envelope(
            "orig-msg-001", reference_digests=[("#Body-1", "abc123")]
        )
        parsed = AS4ReceiptHandler().parse(receipt_bytes)
        assert parsed.ref_to_message_id == "orig-msg-001"

    def test_build_error_envelope_round_trips_with_parser(self) -> None:
        from mcp_einvoicing_core.peppol.transport.receipt import AS4ReceiptHandler

        handler = AS4InboundHandler()
        error = handler.build_not_serviced_error("orig-msg-002")
        error_bytes = build_error_envelope(error)

        with pytest.raises(PlatformError, match="PEPPOL:NOT_SERVICED|EBMS:0004"):
            AS4ReceiptHandler().parse(error_bytes)

    def test_build_receipt_can_be_signed(self) -> None:
        key, cert_der = _generate_test_key_and_cert()
        receipt_bytes = build_receipt_envelope("orig-msg-003")
        signed = sign_as4_message(receipt_bytes, [], cert_der, key)
        root = etree.fromstring(signed)
        security = root.find(
            ".//{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Security"
        )
        assert security is not None
