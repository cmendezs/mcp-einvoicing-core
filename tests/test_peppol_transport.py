"""Tests for Peppol AS4 transport primitives."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree

from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.peppol.transport.client import AS4TransportClient
from mcp_einvoicing_core.peppol.transport.envelope import AS4MessageEnvelope
from mcp_einvoicing_core.peppol.transport.models import AS4Credentials, AS4Receipt
from mcp_einvoicing_core.peppol.transport.receipt import AS4ReceiptHandler


def _generate_test_pem_cert_and_key() -> tuple[bytes, bytes]:
    """Return (cert_pem, key_pem) for a self-signed test certificate."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test AP")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC))
        .not_valid_after(datetime.now(UTC) + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem

SAMPLE_INVOICE = b"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
  <ID>INV-001</ID>
</Invoice>"""


def _make_receipt_xml(message_id: str = "rcpt-001", ref_to: str = "msg-001") -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<S12:Envelope xmlns:S12="http://www.w3.org/2003/05/soap-envelope"
              xmlns:eb="http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/">
  <S12:Header>
    <eb:Messaging>
      <eb:SignalMessage>
        <eb:MessageInfo>
          <eb:Timestamp>2026-06-25T10:00:00Z</eb:Timestamp>
          <eb:MessageId>{message_id}</eb:MessageId>
          <eb:RefToMessageId>{ref_to}</eb:RefToMessageId>
        </eb:MessageInfo>
        <eb:Receipt>
          <NonRepudiationInformation>
            <MessagePartNRInformation>
              <ds:DigestValue xmlns:ds="http://www.w3.org/2000/09/xmldsig#">abc123</ds:DigestValue>
            </MessagePartNRInformation>
          </NonRepudiationInformation>
        </eb:Receipt>
      </eb:SignalMessage>
    </eb:Messaging>
  </S12:Header>
  <S12:Body/>
</S12:Envelope>""".encode()


def _make_error_xml(error_code: str = "EBMS:0004", description: str = "Error") -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<S12:Envelope xmlns:S12="http://www.w3.org/2003/05/soap-envelope"
              xmlns:eb="http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/">
  <S12:Header>
    <eb:Messaging>
      <eb:SignalMessage>
        <eb:Error errorCode="{error_code}" shortDescription="{description}"/>
      </eb:SignalMessage>
    </eb:Messaging>
  </S12:Header>
  <S12:Body/>
</S12:Envelope>""".encode()


class TestAS4MessageEnvelope:
    def test_build_produces_valid_soap(self) -> None:
        envelope = AS4MessageEnvelope(
            sender_id="POP000001",
            receiver_id="0204:991-1234512345-06",
            document_type_id="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::Invoice",
            process_id="urn:fdc:peppol.eu:2017:poacc:billing:01:1.0",
            payload_xml=SAMPLE_INVOICE,
            message_id="test-msg-001",
        )
        xml_bytes = envelope.build()

        root = etree.fromstring(xml_bytes)
        assert root.tag == "{http://www.w3.org/2003/05/soap-envelope}Envelope"

        messaging = root.find(
            ".//{http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/}Messaging"
        )
        assert messaging is not None

        msg_id = root.find(
            ".//{http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/}MessageId"
        )
        assert msg_id is not None
        assert msg_id.text == "test-msg-001"

    def test_build_contains_party_info(self) -> None:
        envelope = AS4MessageEnvelope(
            sender_id="SENDER",
            receiver_id="RECEIVER",
            document_type_id="doc-type",
            process_id="process",
            payload_xml=SAMPLE_INVOICE,
        )
        xml_bytes = envelope.build()
        root = etree.fromstring(xml_bytes)

        from_party = root.find(
            ".//{http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/}From"
            "/{http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/}PartyId"
        )
        assert from_party is not None
        assert from_party.text == "SENDER"

        to_party = root.find(
            ".//{http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/}To"
            "/{http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/}PartyId"
        )
        assert to_party is not None
        assert to_party.text == "RECEIVER"

    def test_build_contains_payload_info(self) -> None:
        envelope = AS4MessageEnvelope(
            sender_id="S",
            receiver_id="R",
            document_type_id="dt",
            process_id="p",
            payload_xml=SAMPLE_INVOICE,
        )
        xml_bytes = envelope.build()
        root = etree.fromstring(xml_bytes)

        part_info = root.find(
            ".//{http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/}PartInfo"
        )
        assert part_info is not None
        assert part_info.get("href") == "cid:invoice@peppol.eu"


class TestAS4ReceiptHandler:
    def test_parse_valid_receipt(self) -> None:
        handler = AS4ReceiptHandler()
        receipt = handler.parse(_make_receipt_xml("rcpt-001", "msg-001"))

        assert receipt.message_id == "rcpt-001"
        assert receipt.ref_to_message_id == "msg-001"
        assert receipt.timestamp.year == 2026
        assert receipt.non_repudiation_information == "abc123"

    def test_parse_error_signal_raises(self) -> None:
        handler = AS4ReceiptHandler()
        with pytest.raises(PlatformError, match="EBMS:0004"):
            handler.parse(_make_error_xml())

    def test_parse_invalid_xml_raises(self) -> None:
        handler = AS4ReceiptHandler()
        with pytest.raises(PlatformError, match="XML parse error"):
            handler.parse(b"not xml")


class TestAS4Credentials:
    def test_load_from_bytes(self) -> None:
        creds = AS4Credentials(
            certificate_bytes=b"CERT_DATA",
            private_key_bytes=b"KEY_DATA",
        )
        assert creds.load_certificate() == b"CERT_DATA"
        assert creds.load_private_key() == b"KEY_DATA"

    def test_missing_certificate_raises(self) -> None:
        creds = AS4Credentials()
        with pytest.raises(ValueError, match="No certificate"):
            creds.load_certificate()

    def test_missing_key_raises(self) -> None:
        creds = AS4Credentials()
        with pytest.raises(ValueError, match="No private key"):
            creds.load_private_key()


class TestAS4Receipt:
    def test_model_fields(self) -> None:
        receipt = AS4Receipt(
            message_id="msg-1",
            ref_to_message_id="ref-1",
            timestamp=datetime(2026, 6, 25, tzinfo=UTC),
        )
        assert receipt.message_id == "msg-1"
        assert receipt.ref_to_message_id == "ref-1"
        assert receipt.non_repudiation_information is None


class TestAS4TransportClientSend:
    async def test_send_signs_envelope_and_posts_multipart(self, httpx_mock) -> None:
        cert_pem, key_pem = _generate_test_pem_cert_and_key()
        credentials = AS4Credentials(certificate_bytes=cert_pem, private_key_bytes=key_pem)
        envelope = AS4MessageEnvelope(
            sender_id="POP000001",
            receiver_id="0204:991-1234512345-06",
            document_type_id="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::Invoice",
            process_id="urn:fdc:peppol.eu:2017:poacc:billing:01:1.0",
            payload_xml=SAMPLE_INVOICE,
            message_id="test-msg-001",
        )

        httpx_mock.add_response(content=_make_receipt_xml(ref_to="test-msg-001"))

        client = AS4TransportClient()
        receipt = await client.send(
            envelope, "https://ap.example.org/as4", credentials
        )

        assert receipt.ref_to_message_id == "test-msg-001"

        request = httpx_mock.get_requests()[0]
        content_type = request.headers["Content-Type"]
        assert content_type.startswith('multipart/related; type="application/soap+xml"')
        boundary = content_type.split('boundary="', 1)[1].rstrip('"')
        body = request.content

        soap_part = body.split(f"--{boundary}".encode())[1]
        soap_xml = soap_part.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n--", 1)[0]
        root = etree.fromstring(soap_xml)
        security = root.find(
            ".//{http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd}Security"
        )
        assert security is not None
