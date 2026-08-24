"""AS4 inbound message receiver (AS4-IN-1, C3 role).

Parses a received AS4 MIME multipart message — the inverse of
``AS4TransportClient._build_multipart_body`` — verifies the WS-Security
signature (see ``wssecurity.verify_as4_signature``), and extracts the SBDH
header and business document from the decompressed payload attachment, per
the Peppol AS4 Profile v2.0.3 section 4.9 ("Use of SBDH"): the SBDH
containing the business message MUST be found in the first MIME attachment
after the MIME attachment containing the AS4 header.

Certificate trust-chain validation of the sender is delegated to
``mcp_einvoicing_core.peppol.trust.validate_certificate_chain`` (guarded —
reports ``trust-anchors-not-configured`` until the OpenPeppol PKI root
certificates are supplied locally).
"""

from __future__ import annotations

import email
import gzip
import logging
from email.message import Message
from email.policy import HTTP

from lxml import etree

from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.peppol import PeppolEnvironment
from mcp_einvoicing_core.peppol.transport.models import (
    AS4InboundError,
    AS4InboundMessage,
    SBDHDocumentIdentification,
    SBDHIdentifier,
    SBDHScope,
    StandardBusinessDocumentHeader,
)
from mcp_einvoicing_core.peppol.transport.wssecurity import SignedAttachment, verify_as4_signature
from mcp_einvoicing_core.xml_utils import safe_fromstring

logger = logging.getLogger(__name__)

_SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
_EBMS_NS = "http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/"
_SBDH_NS = "http://www.unece.org/cefact/namespaces/StandardBusinessDocumentHeader"


def _local(tag: object) -> str | None:
    """Return the local name of an element tag, or None for comments/PIs
    (whose ``.tag`` is a callable, not a string)."""
    if not isinstance(tag, str):
        return None
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find(root: etree._Element, ns: str, local: str) -> etree._Element | None:
    return root.find(f".//{{{ns}}}{local}")


def _findall(root: etree._Element, ns: str, local: str) -> list[etree._Element]:
    return root.findall(f".//{{{ns}}}{local}")


def _text(parent: etree._Element | None, local_name: str) -> str | None:
    if parent is None:
        return None
    for el in parent.iter():
        if _local(el.tag) == local_name:
            return (el.text or "").strip() or None
    return None


class MimeParseError(PlatformError):
    """Raised when the inbound MIME multipart body cannot be parsed."""


def parse_mime_multipart(content_type: str, body: bytes) -> tuple[bytes, dict[str, bytes]]:
    """Split a ``multipart/related`` AS4 message into (soap_bytes, attachments).

    Args:
        content_type: The HTTP ``Content-Type`` header value (carries the
            multipart boundary).
        body: The raw HTTP request body.

    Returns:
        A tuple of the first part's bytes (the SOAP envelope) and a dict
        mapping each subsequent part's ``Content-Id`` (without ``cid:``
        prefix or angle brackets) to its raw bytes.

    Raises:
        MimeParseError: If the body is not a well-formed MIME multipart
            message, or has no SOAP part.
    """
    header_bytes = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
    message: Message = email.message_from_bytes(header_bytes + body, policy=HTTP)

    if not message.is_multipart():
        raise MimeParseError(
            status_code=0, message="AS4 inbound body is not a MIME multipart message."
        )

    parts = list(message.iter_parts())
    if not parts:
        raise MimeParseError(
            status_code=0, message="AS4 inbound MIME multipart message has no parts."
        )

    soap_bytes = parts[0].get_payload(decode=True)
    if soap_bytes is None:
        raise MimeParseError(status_code=0, message="AS4 inbound MIME first part has no payload.")

    attachments: dict[str, bytes] = {}
    for part in parts[1:]:
        content_id = (part.get("Content-Id") or "").strip().strip("<>")
        payload = part.get_payload(decode=True)
        if content_id and payload is not None:
            attachments[content_id] = payload

    return soap_bytes, attachments


def _parse_sbdh(root: etree._Element) -> StandardBusinessDocumentHeader | None:
    header_el = _find(root, _SBDH_NS, "StandardBusinessDocumentHeader")
    if header_el is None:
        return None

    sender_el = _find(header_el, _SBDH_NS, "Sender")
    sender = None
    if sender_el is not None:
        identifier_el = _find(sender_el, _SBDH_NS, "Identifier")
        if identifier_el is not None:
            sender = SBDHIdentifier(
                authority=identifier_el.get("Authority", ""),
                value=(identifier_el.text or "").strip(),
            )

    receiver_el = _find(header_el, _SBDH_NS, "Receiver")
    receiver = None
    if receiver_el is not None:
        identifier_el = _find(receiver_el, _SBDH_NS, "Identifier")
        if identifier_el is not None:
            receiver = SBDHIdentifier(
                authority=identifier_el.get("Authority", ""),
                value=(identifier_el.text or "").strip(),
            )

    doc_id_el = _find(header_el, _SBDH_NS, "DocumentIdentification")
    doc_id = None
    if doc_id_el is not None:
        doc_id = SBDHDocumentIdentification(
            standard=_text(doc_id_el, "Standard"),
            type_version=_text(doc_id_el, "TypeVersion"),
            instance_identifier=_text(doc_id_el, "InstanceIdentifier"),
            type=_text(doc_id_el, "Type"),
            creation_date_and_time=_text(doc_id_el, "CreationDateAndTime"),
        )

    scopes: list[SBDHScope] = []
    business_scope_el = _find(header_el, _SBDH_NS, "BusinessScope")
    if business_scope_el is not None:
        for scope_el in business_scope_el:
            if _local(scope_el.tag) != "Scope":
                continue
            scopes.append(
                SBDHScope(
                    type=_text(scope_el, "Type") or "",
                    instance_identifier=_text(scope_el, "InstanceIdentifier"),
                    identifier=_text(scope_el, "Identifier"),
                )
            )

    return StandardBusinessDocumentHeader(
        header_version=_text(header_el, "HeaderVersion"),
        sender=sender,
        receiver=receiver,
        document_identification=doc_id,
        business_scope=scopes,
    )


def _extract_business_document(root: etree._Element) -> bytes | None:
    """Return the serialized business document: the sibling of
    ``StandardBusinessDocumentHeader`` under ``StandardBusinessDocument``."""
    if _local(root.tag) != "StandardBusinessDocument":
        # Not SBDH-wrapped; treat the whole payload as the business document.
        return etree.tostring(root)
    for child in root:
        if _local(child.tag) != "StandardBusinessDocumentHeader":
            return etree.tostring(child)
    return None


class AS4InboundHandler:
    """Receives and validates inbound Peppol AS4 UserMessages (C3 role)."""

    def receive(
        self,
        content_type: str,
        body: bytes,
        *,
        environment: PeppolEnvironment = PeppolEnvironment.PRODUCTION,
        verify_signature: bool = True,
    ) -> AS4InboundMessage:
        """Parse and validate an inbound AS4 message.

        Args:
            content_type: The HTTP ``Content-Type`` header of the request.
            body: The raw HTTP request body.
            environment: Which OpenPeppol PKI environment to chain-validate
                the sender certificate against (only used when
                ``verify_signature`` is True — guarded, see
                ``mcp_einvoicing_core.peppol.trust``).
            verify_signature: Verify the ``wsse:Security`` signature and
                chain-validate the sender certificate. Never raises on
                verification failure — failures are reported on the
                returned `AS4InboundMessage` (``signature_valid=False``)
                so callers can decide whether to still process the message.

        Raises:
            MimeParseError: If the MIME multipart body cannot be parsed.
            PlatformError: If the SOAP envelope is malformed or has no
                ``eb:UserMessage``.
        """
        soap_bytes, raw_attachments = parse_mime_multipart(content_type, body)

        try:
            root = safe_fromstring(soap_bytes)
        except etree.XMLSyntaxError as exc:
            raise PlatformError(
                status_code=0, message=f"AS4 SOAP envelope XML parse error: {exc}"
            ) from exc

        user_message = _find(root, _EBMS_NS, "UserMessage")
        if user_message is None:
            raise PlatformError(status_code=0, message="AS4 SOAP envelope has no eb:UserMessage.")

        message_id = _text(user_message, "MessageId") or ""
        conversation_id = _text(user_message, "ConversationId")
        service = _text(user_message, "Service")
        action = _text(user_message, "Action")

        sender_id = None
        receiver_id = None
        for party_id_el in _findall(user_message, _EBMS_NS, "PartyId"):
            from_el = party_id_el.getparent()
            role_parent_local = _local(from_el.tag) if from_el is not None else ""
            if role_parent_local == "From" and sender_id is None:
                sender_id = (party_id_el.text or "").strip() or None
            elif role_parent_local == "To" and receiver_id is None:
                receiver_id = (party_id_el.text or "").strip() or None

        signature_valid: bool | None = None
        signature_error: str | None = None
        signer_cert_der: bytes | None = None
        chain_validation: dict | None = None

        if verify_signature:
            attachments = [
                SignedAttachment(content_id=cid, content=content)
                for cid, content in raw_attachments.items()
            ]
            sig_result = verify_as4_signature(soap_bytes, attachments)
            signature_valid = sig_result.signature_valid
            signature_error = sig_result.error
            signer_cert_der = sig_result.certificate_der
            if signer_cert_der is not None:
                from mcp_einvoicing_core.peppol.trust import (
                    validate_certificate_chain,  # noqa: PLC0415
                )

                chain_validation = validate_certificate_chain(signer_cert_der, environment)

        sbdh: StandardBusinessDocumentHeader | None = None
        business_document_xml: bytes | None = None
        if raw_attachments:
            # Peppol AS4 Profile 2.0.3 section 4.9: the SBDH-wrapped business
            # message is the first MIME attachment after the AS4 header.
            first_attachment = next(iter(raw_attachments.values()))
            try:
                decompressed = gzip.decompress(first_attachment)
            except OSError:
                decompressed = first_attachment
            try:
                payload_root = safe_fromstring(decompressed)
                sbdh = _parse_sbdh(payload_root)
                business_document_xml = _extract_business_document(payload_root)
            except etree.XMLSyntaxError as exc:
                logger.warning("Could not parse SBDH/business document payload: %s", exc)

        return AS4InboundMessage(
            message_id=message_id,
            conversation_id=conversation_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            service=service,
            action=action,
            sbdh=sbdh,
            business_document_xml=business_document_xml,
            signature_valid=signature_valid,
            signature_error=signature_error,
            signer_certificate_der=signer_cert_der,
            chain_validation=chain_validation,
            raw_soap_xml=soap_bytes,
        )

    def build_not_serviced_error(self, ref_to_message_id: str) -> AS4InboundError:
        """Return the standard error to send back when the addressed
        participant/document type is not serviced by this Access Point.

        Peppol AS4 Profile 2.0.3 section 4.4: ``EBMS:0004`` / severity
        ``failure`` / errorDetail ``PEPPOL:NOT_SERVICED``.
        """
        return AS4InboundError(ref_to_message_id=ref_to_message_id)
