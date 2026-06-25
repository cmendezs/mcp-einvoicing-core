"""Tests for Peppol AS4 transport primitives."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from lxml import etree

from mcp_einvoicing_core.peppol.transport.envelope import AS4MessageEnvelope
from mcp_einvoicing_core.peppol.transport.models import AS4Credentials, AS4Receipt
from mcp_einvoicing_core.peppol.transport.receipt import AS4ReceiptHandler
from mcp_einvoicing_core.exceptions import PlatformError


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
            timestamp=datetime(2026, 6, 25, tzinfo=timezone.utc),
        )
        assert receipt.message_id == "msg-1"
        assert receipt.ref_to_message_id == "ref-1"
        assert receipt.non_repudiation_information is None
