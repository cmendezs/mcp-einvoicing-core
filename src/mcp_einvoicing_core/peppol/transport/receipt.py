"""AS4 receipt (signal message) parsing and generation."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from lxml import etree

from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.peppol.transport.models import AS4InboundError, AS4Receipt
from mcp_einvoicing_core.xml_utils import safe_fromstring

logger = logging.getLogger(__name__)

_EBMS_NS = "http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/"
_SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"

_NSMAP = {"S12": _SOAP_NS, "eb": _EBMS_NS}


def _qn(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


def build_receipt_envelope(
    ref_to_message_id: str,
    *,
    reference_digests: list[tuple[str, str]] | None = None,
    message_id: str | None = None,
) -> bytes:
    """Build an unsigned ebMS3 AS4 receipt (SignalMessage/Receipt) SOAP envelope.

    Args:
        ref_to_message_id: The ``MessageId`` of the UserMessage being
            acknowledged.
        reference_digests: Optional ``(uri, digest_b64)`` pairs to echo back
            as ``MessagePartNRInformation`` (non-repudiation of receipt),
            normally the ``ds:Reference`` entries verified from the inbound
            message's ``wsse:Security`` signature.
        message_id: MessageId for this receipt signal message. Generated if
            not supplied.

    Returns:
        UTF-8 XML bytes of the SOAP envelope. Pass to
        ``wssecurity.sign_as4_message(receipt_bytes, [], cert_der, key)``
        to sign it before sending, per the Peppol AS4 Profile's use of the
        Peppol PKI for all message-level security.
    """
    envelope = etree.Element(_qn(_SOAP_NS, "Envelope"), nsmap=_NSMAP)
    header = etree.SubElement(envelope, _qn(_SOAP_NS, "Header"))
    messaging = etree.SubElement(header, _qn(_EBMS_NS, "Messaging"))
    signal = etree.SubElement(messaging, _qn(_EBMS_NS, "SignalMessage"))

    msg_info = etree.SubElement(signal, _qn(_EBMS_NS, "MessageInfo"))
    ts = etree.SubElement(msg_info, _qn(_EBMS_NS, "Timestamp"))
    ts.text = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    etree.SubElement(msg_info, _qn(_EBMS_NS, "MessageId")).text = message_id or str(uuid.uuid4())
    etree.SubElement(msg_info, _qn(_EBMS_NS, "RefToMessageId")).text = ref_to_message_id

    receipt = etree.SubElement(signal, _qn(_EBMS_NS, "Receipt"))
    if reference_digests:
        nri = etree.SubElement(receipt, "NonRepudiationInformation")
        for uri, digest_b64 in reference_digests:
            mpni = etree.SubElement(nri, "MessagePartNRInformation")
            ref = etree.SubElement(
                mpni, "{http://www.w3.org/2000/09/xmldsig#}Reference", nsmap={"ds": "http://www.w3.org/2000/09/xmldsig#"}
            )
            ref.set("URI", uri)
            etree.SubElement(ref, "{http://www.w3.org/2000/09/xmldsig#}DigestValue").text = digest_b64

    etree.SubElement(envelope, _qn(_SOAP_NS, "Body"))

    return etree.tostring(envelope, xml_declaration=True, encoding="UTF-8")


def build_error_envelope(error: AS4InboundError, *, message_id: str | None = None) -> bytes:
    """Build an ebMS3 AS4 Error signal message SOAP envelope.

    Per the Peppol AS4 Profile 2.0.3 section 4.4 ("Feedback when receiver
    is not serviced"), sent when the addressed participant/document type
    is not serviced by this Access Point.
    """
    envelope = etree.Element(_qn(_SOAP_NS, "Envelope"), nsmap=_NSMAP)
    header = etree.SubElement(envelope, _qn(_SOAP_NS, "Header"))
    messaging = etree.SubElement(header, _qn(_EBMS_NS, "Messaging"))
    signal = etree.SubElement(messaging, _qn(_EBMS_NS, "SignalMessage"))

    msg_info = etree.SubElement(signal, _qn(_EBMS_NS, "MessageInfo"))
    ts = etree.SubElement(msg_info, _qn(_EBMS_NS, "Timestamp"))
    ts.text = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    etree.SubElement(msg_info, _qn(_EBMS_NS, "MessageId")).text = message_id or str(uuid.uuid4())
    if error.ref_to_message_id:
        etree.SubElement(msg_info, _qn(_EBMS_NS, "RefToMessageId")).text = error.ref_to_message_id

    error_el = etree.SubElement(signal, _qn(_EBMS_NS, "Error"))
    error_el.set("errorCode", error.error_code)
    error_el.set("severity", error.severity)
    error_el.set("shortDescription", error.short_description)
    etree.SubElement(error_el, _qn(_EBMS_NS, "ErrorDetail")).text = error.error_detail

    etree.SubElement(envelope, _qn(_SOAP_NS, "Body"))

    return etree.tostring(envelope, xml_declaration=True, encoding="UTF-8")


class AS4ReceiptHandler:
    """Parses the synchronous AS4 receipt signal message.

    The receiving Access Point returns a SOAP envelope containing an
    eb:SignalMessage with a eb:Receipt element. This handler extracts
    the MessageId, RefToMessageId, Timestamp, and optional
    NonRepudiationInformation digest.
    """

    def parse(self, response_bytes: bytes) -> AS4Receipt:
        """Parse an AS4 receipt from the HTTP response body.

        Args:
            response_bytes: Raw XML bytes of the SOAP response.

        Returns:
            Parsed AS4Receipt model.

        Raises:
            PlatformError: If the response cannot be parsed or contains
                an AS4 error signal instead of a receipt.
        """
        try:
            root = safe_fromstring(response_bytes)
        except etree.XMLSyntaxError as exc:
            raise PlatformError(
                status_code=0,
                message=f"AS4 receipt XML parse error: {exc}",
            ) from exc

        error_el = self._find_element(root, "Error")
        if error_el is not None:
            error_detail = error_el.get("shortDescription", "")
            error_code = error_el.get("errorCode", "")
            raise PlatformError(
                status_code=0,
                message=(
                    f"AS4 error signal received: {error_code} {error_detail}"
                ),
            )

        signal = self._find_element(root, "SignalMessage")
        if signal is None:
            raise PlatformError(
                status_code=0,
                message="AS4 response does not contain a SignalMessage element.",
            )

        message_id = self._find_text(signal, "MessageId") or ""
        ref_to = self._find_text(signal, "RefToMessageId") or ""
        timestamp_str = self._find_text(signal, "Timestamp")

        timestamp: datetime
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                )
            except ValueError:
                timestamp = datetime.now(UTC)
        else:
            timestamp = datetime.now(UTC)

        nri = self._find_text(signal, "DigestValue")

        return AS4Receipt(
            message_id=message_id,
            ref_to_message_id=ref_to,
            timestamp=timestamp,
            non_repudiation_information=nri,
            raw_xml=response_bytes,
        )

    def _find_element(
        self, root: etree._Element, local_name: str
    ) -> etree._Element | None:
        for el in root.iter():
            tag_local = etree.QName(el.tag).localname if "{" in el.tag else el.tag
            if tag_local == local_name:
                return el
        return None

    def _find_text(
        self, parent: etree._Element, local_name: str
    ) -> str | None:
        el = self._find_element(parent, local_name)
        if el is not None:
            return (el.text or "").strip() or None
        return None
