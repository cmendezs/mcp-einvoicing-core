"""AS4 HTTP transport client with TLS and message-level signing."""

from __future__ import annotations

import gzip
import logging
import uuid

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.x509 import load_pem_x509_certificate

from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.peppol.transport.envelope import AS4MessageEnvelope
from mcp_einvoicing_core.peppol.transport.models import AS4Credentials, AS4Receipt
from mcp_einvoicing_core.peppol.transport.receipt import AS4ReceiptHandler
from mcp_einvoicing_core.peppol.transport.wssecurity import SignedAttachment, sign_as4_message

logger = logging.getLogger(__name__)

_ATTACHMENT_CONTENT_ID = "invoice@peppol.eu"


class AS4TransportClient:
    """HTTP client for sending AS4 user messages to a Peppol Access Point.

    Handles MIME multipart construction, payload compression (gzip),
    and X.509 message-level signing per the Peppol AS4 profile.
    """

    def __init__(self, http_timeout: float = 30.0) -> None:
        self._http_timeout = http_timeout
        self._receipt_handler = AS4ReceiptHandler()

    async def send(
        self,
        envelope: AS4MessageEnvelope,
        endpoint_url: str,
        credentials: AS4Credentials,
    ) -> AS4Receipt:
        """Send an AS4 UserMessage and parse the synchronous receipt.

        Args:
            envelope: The constructed ebMS3 envelope.
            endpoint_url: The AS4 endpoint URL of the receiving Access Point.
            credentials: Signing certificate and private key.

        Returns:
            Parsed AS4Receipt from the synchronous signal message response.

        Raises:
            PlatformError: On HTTP errors or invalid receipt responses.
        """
        soap_bytes = envelope.build()
        compressed_payload = gzip.compress(envelope.payload_xml)

        signed_soap_bytes = self._apply_message_signature(
            soap_bytes, compressed_payload, credentials
        )

        boundary = f"----=_Part_{uuid.uuid4().hex}"
        content_type = (
            f'multipart/related; type="application/soap+xml"; '
            f'boundary="{boundary}"'
        )

        body = self._build_multipart_body(
            signed_soap_bytes, compressed_payload, boundary
        )

        headers = {
            "Content-Type": content_type,
            "SOAPAction": "",
            "Message-Id": envelope.message_id,
        }

        logger.debug("AS4 send to %s (message_id=%s)", endpoint_url, envelope.message_id)

        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            response = await client.post(
                endpoint_url,
                content=body,
                headers=headers,
            )

        if not response.is_success:
            raise PlatformError(
                status_code=response.status_code,
                message=(
                    f"AS4 endpoint returned HTTP {response.status_code}: "
                    f"{response.text[:500]}"
                ),
            )

        receipt = self._receipt_handler.parse(response.content)
        if receipt.ref_to_message_id != envelope.message_id:
            logger.warning(
                "AS4 receipt RefToMessageId mismatch: expected %s, got %s",
                envelope.message_id,
                receipt.ref_to_message_id,
            )

        return receipt

    def _build_multipart_body(
        self,
        soap_bytes: bytes,
        compressed_payload: bytes,
        boundary: str,
    ) -> bytes:
        """Build MIME multipart/related body with SOAP part and payload attachment."""
        parts: list[bytes] = []
        crlf = b"\r\n"
        dash_boundary = f"--{boundary}".encode()

        # SOAP part
        parts.append(dash_boundary)
        parts.append(b"Content-Type: application/soap+xml; charset=UTF-8")
        parts.append(b"Content-Transfer-Encoding: binary")
        parts.append(b"")
        parts.append(soap_bytes)

        # Payload attachment
        parts.append(dash_boundary)
        parts.append(b"Content-Type: application/gzip")
        parts.append(b"Content-Transfer-Encoding: binary")
        parts.append(b"Content-Id: <invoice@peppol.eu>")
        parts.append(b"")
        parts.append(compressed_payload)

        # Closing boundary
        parts.append(f"--{boundary}--".encode())

        return crlf.join(parts)

    def _apply_message_signature(
        self,
        soap_bytes: bytes,
        compressed_payload: bytes,
        credentials: AS4Credentials,
    ) -> bytes:
        """Apply WS-Security X.509 message-level signature to the SOAP envelope.

        Builds a wsse:Security header (BinarySecurityToken + ds:Signature)
        covering the SOAP Body, the eb:Messaging header, and the compressed
        invoice attachment, per the Peppol AS4 Profile 2.0.3 section 4.7.
        See ``mcp_einvoicing_core.peppol.transport.wssecurity`` for the wire
        format details.
        """
        cert_bytes = credentials.load_certificate()
        key_bytes = credentials.load_private_key()

        password = (
            credentials.private_key_password.encode()
            if credentials.private_key_password
            else None
        )

        private_key = serialization.load_pem_private_key(key_bytes, password=password)
        cert = load_pem_x509_certificate(cert_bytes)
        cert_der = cert.public_bytes(serialization.Encoding.DER)

        signed_soap_bytes = sign_as4_message(
            soap_bytes,
            [SignedAttachment(content_id=_ATTACHMENT_CONTENT_ID, content=compressed_payload)],
            cert_der,
            private_key,
        )

        logger.debug("AS4 message signed (%d bytes)", len(signed_soap_bytes))

        return signed_soap_bytes
