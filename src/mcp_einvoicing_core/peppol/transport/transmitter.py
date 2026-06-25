"""High-level Peppol AS4 transmitter combining lookup, envelope, send, and receipt."""

from __future__ import annotations

import logging
from typing import Optional

from mcp_einvoicing_core.peppol import (
    PEPPOL_BIS_BILLING_30,
    PeppolEnvironment,
    PeppolParticipantId,
    PeppolSMPClient,
)
from mcp_einvoicing_core.peppol.transport.client import AS4TransportClient
from mcp_einvoicing_core.peppol.transport.envelope import AS4MessageEnvelope
from mcp_einvoicing_core.peppol.transport.models import AS4Credentials, AS4Receipt
from mcp_einvoicing_core.exceptions import PlatformError

logger = logging.getLogger(__name__)

_PEPPOL_BIS_PROCESS = (
    "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"
)


class PeppolTransmitter:
    """Convenience wrapper for end-to-end Peppol AS4 invoice transmission.

    Combines:
    1. PeppolSMPClient.lookup_participant + get_service_endpoint (endpoint discovery)
    2. AS4MessageEnvelope construction (ebMS3 SOAP envelope)
    3. AS4TransportClient.send (HTTP POST with signing)
    4. AS4ReceiptHandler.parse (receipt validation)

    Usage::

        transmitter = PeppolTransmitter(credentials=creds)
        receipt = await transmitter.transmit(
            invoice_xml=xml_bytes,
            recipient_id=PeppolParticipantId.parse("0204:991-1234512345-06"),
            sender_id="POP000001",
        )
        print(receipt.message_id)
    """

    def __init__(
        self,
        credentials: AS4Credentials,
        environment: PeppolEnvironment = PeppolEnvironment.PRODUCTION,
        *,
        document_type_id: str = PEPPOL_BIS_BILLING_30,
        process_id: str = _PEPPOL_BIS_PROCESS,
        http_timeout: float = 30.0,
    ) -> None:
        self._credentials = credentials
        self._smp_client = PeppolSMPClient(environment=environment)
        self._transport_client = AS4TransportClient(http_timeout=http_timeout)
        self._document_type_id = document_type_id
        self._process_id = process_id

    async def transmit(
        self,
        invoice_xml: bytes,
        recipient_id: PeppolParticipantId,
        sender_id: str,
        *,
        document_type_id: Optional[str] = None,
        process_id: Optional[str] = None,
    ) -> AS4Receipt:
        """Transmit an invoice to a Peppol participant via AS4.

        Args:
            invoice_xml: UBL or CII invoice XML bytes.
            recipient_id: Peppol participant identifier of the receiver.
            sender_id: Peppol AP identifier of the sender.
            document_type_id: Override the default document type identifier.
            process_id: Override the default process identifier.

        Returns:
            AS4Receipt with the message ID and receipt status.

        Raises:
            PlatformError: If the recipient is not registered, endpoint
                discovery fails, or the AS4 transmission fails.
        """
        doc_type = document_type_id or self._document_type_id
        proc_id = process_id or self._process_id

        logger.info(
            "Peppol transmit: recipient=%s, doc_type=%s",
            recipient_id,
            doc_type[:80],
        )

        lookup = await self._smp_client.lookup_participant(recipient_id)
        if not lookup.is_registered:
            raise PlatformError(
                status_code=0,
                message=(
                    f"Recipient {recipient_id} is not registered on the "
                    f"Peppol network: {lookup.error or 'not found'}"
                ),
            )

        service_info = await self._smp_client.get_service_endpoint(
            participant_id=recipient_id,
            document_type_id=doc_type,
            smp_hostname=lookup.smp_hostname,
        )

        if not service_info.endpoint_url:
            raise PlatformError(
                status_code=0,
                message=(
                    f"No AS4 endpoint found for {recipient_id} with "
                    f"document type {doc_type}"
                ),
            )

        envelope = AS4MessageEnvelope(
            sender_id=sender_id,
            receiver_id=str(recipient_id),
            document_type_id=doc_type,
            process_id=proc_id,
            payload_xml=invoice_xml,
        )

        receipt = await self._transport_client.send(
            envelope=envelope,
            endpoint_url=service_info.endpoint_url,
            credentials=self._credentials,
        )

        logger.info(
            "Peppol transmit success: message_id=%s, receipt_id=%s",
            envelope.message_id,
            receipt.message_id,
        )

        return receipt
