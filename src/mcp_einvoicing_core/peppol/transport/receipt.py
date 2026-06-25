"""AS4 receipt (signal message) parser."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from lxml import etree

from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.peppol.transport.models import AS4Receipt
from mcp_einvoicing_core.xml_utils import safe_fromstring

logger = logging.getLogger(__name__)

_EBMS_NS = "http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/ns/core/200704/"
_SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"


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
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

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
    ) -> Optional[etree._Element]:
        for el in root.iter():
            tag_local = etree.QName(el.tag).localname if "{" in el.tag else el.tag
            if tag_local == local_name:
                return el
        return None

    def _find_text(
        self, parent: etree._Element, local_name: str
    ) -> Optional[str]:
        el = self._find_element(parent, local_name)
        if el is not None:
            return (el.text or "").strip() or None
        return None
