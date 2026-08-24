"""Peppol AS4 outbound transmission primitives.

Provides the transport layer for sending invoices via the Peppol AS4 profile,
building on the existing PeppolSMPClient for endpoint discovery.

References:
  OpenPeppol AS4 Profile 2.0: https://docs.peppol.eu/edelivery/as4/specification/
  ebMS3 Core Specification:   http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/core/
  ETSI REM Evidence:          ETSI EN 319 532-4
"""

from mcp_einvoicing_core.peppol.transport.client import AS4TransportClient
from mcp_einvoicing_core.peppol.transport.envelope import AS4MessageEnvelope
from mcp_einvoicing_core.peppol.transport.inbound import (
    AS4InboundHandler,
    MimeParseError,
    parse_mime_multipart,
)
from mcp_einvoicing_core.peppol.transport.models import (
    AS4Credentials,
    AS4InboundError,
    AS4InboundMessage,
    AS4Receipt,
    SBDHDocumentIdentification,
    SBDHIdentifier,
    SBDHScope,
    StandardBusinessDocumentHeader,
)
from mcp_einvoicing_core.peppol.transport.receipt import (
    AS4ReceiptHandler,
    build_error_envelope,
    build_receipt_envelope,
)
from mcp_einvoicing_core.peppol.transport.transmitter import PeppolTransmitter
from mcp_einvoicing_core.peppol.transport.wssecurity import (
    AS4SignatureVerificationResult,
    SignedAttachment,
    sign_as4_message,
    verify_as4_signature,
)

__all__ = [
    "AS4Credentials",
    "AS4MessageEnvelope",
    "AS4Receipt",
    "AS4ReceiptHandler",
    "AS4TransportClient",
    "PeppolTransmitter",
    # AS4-IN-1 inbound receiver
    "AS4InboundHandler",
    "AS4InboundMessage",
    "AS4InboundError",
    "MimeParseError",
    "parse_mime_multipart",
    "build_receipt_envelope",
    "build_error_envelope",
    # SBDH models
    "StandardBusinessDocumentHeader",
    "SBDHIdentifier",
    "SBDHDocumentIdentification",
    "SBDHScope",
    # WS-Security signing/verification
    "SignedAttachment",
    "sign_as4_message",
    "verify_as4_signature",
    "AS4SignatureVerificationResult",
]
