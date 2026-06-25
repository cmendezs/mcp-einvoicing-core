"""ebMS3 / AS4 SOAP envelope construction for Peppol outbound messages."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from lxml import etree

_SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
_EBMS_NS = "http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/"
_WSA_NS = "http://www.w3.org/2005/08/addressing"
_MIME_NS = "http://www.w3.org/2004/06/xmlmime"

_PEPPOL_AS4_ACTION = "http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/oneWay"
_PEPPOL_AS4_SERVICE = (
    "http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/service"
)

NSMAP = {
    "S12": _SOAP_NS,
    "eb": _EBMS_NS,
    "wsa": _WSA_NS,
}


class AS4MessageEnvelope:
    """Constructs an ebMS3/AS4 SOAP envelope wrapping an invoice payload.

    The envelope follows the Peppol AS4 profile structure:
    - <S12:Envelope>
      - <S12:Header>
        - <eb:Messaging>
          - <eb:UserMessage>
            - <eb:MessageInfo>
            - <eb:PartyInfo>
            - <eb:CollaborationInfo>
            - <eb:PayloadInfo>
      - <S12:Body/>
    """

    def __init__(
        self,
        sender_id: str,
        receiver_id: str,
        document_type_id: str,
        process_id: str,
        payload_xml: bytes,
        *,
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> None:
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.document_type_id = document_type_id
        self.process_id = process_id
        self.payload_xml = payload_xml
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.message_id = message_id or str(uuid.uuid4())
        self.timestamp = datetime.now(timezone.utc)

    def build(self) -> bytes:
        """Build the complete SOAP envelope as XML bytes."""
        envelope = etree.Element(f"{{{_SOAP_NS}}}Envelope", nsmap=NSMAP)

        header = etree.SubElement(envelope, f"{{{_SOAP_NS}}}Header")
        self._build_messaging(header)

        etree.SubElement(envelope, f"{{{_SOAP_NS}}}Body")

        return etree.tostring(envelope, xml_declaration=True, encoding="UTF-8")

    def _build_messaging(self, header: etree._Element) -> None:
        messaging = etree.SubElement(header, f"{{{_EBMS_NS}}}Messaging")
        user_message = etree.SubElement(messaging, f"{{{_EBMS_NS}}}UserMessage")

        self._build_message_info(user_message)
        self._build_party_info(user_message)
        self._build_collaboration_info(user_message)
        self._build_payload_info(user_message)

    def _build_message_info(self, user_message: etree._Element) -> None:
        msg_info = etree.SubElement(user_message, f"{{{_EBMS_NS}}}MessageInfo")

        ts = etree.SubElement(msg_info, f"{{{_EBMS_NS}}}Timestamp")
        ts.text = self.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        mid = etree.SubElement(msg_info, f"{{{_EBMS_NS}}}MessageId")
        mid.text = self.message_id

    def _build_party_info(self, user_message: etree._Element) -> None:
        party_info = etree.SubElement(user_message, f"{{{_EBMS_NS}}}PartyInfo")

        from_el = etree.SubElement(party_info, f"{{{_EBMS_NS}}}From")
        from_party = etree.SubElement(from_el, f"{{{_EBMS_NS}}}PartyId")
        from_party.set("type", "urn:fdc:peppol.eu:2017:identifiers:ap")
        from_party.text = self.sender_id
        from_role = etree.SubElement(from_el, f"{{{_EBMS_NS}}}Role")
        from_role.text = "http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/initiator"

        to_el = etree.SubElement(party_info, f"{{{_EBMS_NS}}}To")
        to_party = etree.SubElement(to_el, f"{{{_EBMS_NS}}}PartyId")
        to_party.set("type", "urn:fdc:peppol.eu:2017:identifiers:ap")
        to_party.text = self.receiver_id
        to_role = etree.SubElement(to_el, f"{{{_EBMS_NS}}}Role")
        to_role.text = "http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/responder"

    def _build_collaboration_info(self, user_message: etree._Element) -> None:
        collab = etree.SubElement(user_message, f"{{{_EBMS_NS}}}CollaborationInfo")

        agreement = etree.SubElement(collab, f"{{{_EBMS_NS}}}AgreementRef")
        agreement.text = "urn:fdc:peppol.eu:2017:agreements:tia:ap_provider"

        service = etree.SubElement(collab, f"{{{_EBMS_NS}}}Service")
        service.set("type", "cenbii-procid-ubl")
        service.text = self.process_id

        action = etree.SubElement(collab, f"{{{_EBMS_NS}}}Action")
        action.text = self.document_type_id

        conv_id = etree.SubElement(collab, f"{{{_EBMS_NS}}}ConversationId")
        conv_id.text = self.conversation_id

    def _build_payload_info(self, user_message: etree._Element) -> None:
        payload_info = etree.SubElement(user_message, f"{{{_EBMS_NS}}}PayloadInfo")

        part_info = etree.SubElement(payload_info, f"{{{_EBMS_NS}}}PartInfo")
        part_info.set("href", "cid:invoice@peppol.eu")

        part_props = etree.SubElement(part_info, f"{{{_EBMS_NS}}}PartProperties")

        mime_prop = etree.SubElement(part_props, f"{{{_EBMS_NS}}}Property")
        mime_prop.set("name", "MimeType")
        mime_prop.text = "application/xml"

        compress_prop = etree.SubElement(part_props, f"{{{_EBMS_NS}}}Property")
        compress_prop.set("name", "CompressionType")
        compress_prop.text = "application/gzip"
