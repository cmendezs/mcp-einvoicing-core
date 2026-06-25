"""Peppol AS4 outbound transmission primitives.

Provides the transport layer for sending invoices via the Peppol AS4 profile,
building on the existing PeppolSMPClient for endpoint discovery.

References:
  OpenPeppol AS4 Profile 2.0: https://docs.peppol.eu/edelivery/as4/specification/
  ebMS3 Core Specification:   http://docs.oasis-open.org/ebxml-msg/ebms/v3.0/core/
  ETSI REM Evidence:          ETSI EN 319 532-4
"""

from mcp_einvoicing_core.peppol.transport.models import (
    AS4Credentials,
    AS4Receipt,
)
from mcp_einvoicing_core.peppol.transport.envelope import AS4MessageEnvelope
from mcp_einvoicing_core.peppol.transport.client import AS4TransportClient
from mcp_einvoicing_core.peppol.transport.receipt import AS4ReceiptHandler
from mcp_einvoicing_core.peppol.transport.transmitter import PeppolTransmitter

__all__ = [
    "AS4Credentials",
    "AS4MessageEnvelope",
    "AS4Receipt",
    "AS4ReceiptHandler",
    "AS4TransportClient",
    "PeppolTransmitter",
]
