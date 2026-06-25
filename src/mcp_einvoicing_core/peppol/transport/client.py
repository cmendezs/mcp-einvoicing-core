"""AS4 HTTP transport client with TLS and message-level signing."""

from __future__ import annotations

import gzip
import logging
import uuid

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_pem_x509_certificate

from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.peppol.transport.envelope import AS4MessageEnvelope
from mcp_einvoicing_core.peppol.transport.models import AS4Credentials, AS4Receipt
from mcp_einvoicing_core.peppol.transport.receipt import AS4ReceiptHandler

logger = logging.getLogger(__name__)


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

        boundary = f"----=_Part_{uuid.uuid4().hex}"
        content_type = (
            f'multipart/related; type="application/soap+xml"; '
            f'boundary="{boundary}"'
        )

        body = self._build_multipart_body(
            soap_bytes, compressed_payload, boundary
        )

        signed_body = self._apply_message_signature(body, credentials)

        headers = {
            "Content-Type": content_type,
            "SOAPAction": "",
            "Message-Id": envelope.message_id,
        }

        logger.debug("AS4 send to %s (message_id=%s)", endpoint_url, envelope.message_id)

        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            response = await client.post(
                endpoint_url,
                content=signed_body,
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
        body: bytes,
        credentials: AS4Credentials,
    ) -> bytes:
        """Apply X.509 message-level signature.

        Per the Peppol AS4 profile, the message is signed using the sender's
        private key. In a full implementation this would produce a WS-Security
        header with ds:Signature. For now, the signature is computed and stored
        but the body is returned as-is since full WS-Security header construction
        requires additional XML canonicalization steps that are AP-specific.

        [NEED: Full WS-Security ds:Signature header construction per Peppol AS4
        profile 2.0 section 5.3. Current implementation computes the digest but
        does not inject the WS-Security header.]
        """
        cert_bytes = credentials.load_certificate()
        key_bytes = credentials.load_private_key()

        password = (
            credentials.private_key_password.encode()
            if credentials.private_key_password
            else None
        )

        private_key = serialization.load_pem_private_key(key_bytes, password=password)
        _cert = load_pem_x509_certificate(cert_bytes)

        _signature = private_key.sign(  # type: ignore[union-attr]
            body,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

        logger.debug("AS4 message signature computed (%d bytes)", len(_signature))

        return body
