"""
mcp-einvoicing-core — Base package for European electronic invoicing MCP servers.

Provides abstract base classes, shared Pydantic models, XML utilities, an HTTP client
with OAuth2 support, and a plugin registry so country packages register their tools
without modifying the base server.

Country packages import from here and register via EInvoicingMCPServer.register_plugin().
"""

from mcp_einvoicing_core.base_server import (
    BaseDocumentGenerator,
    BaseDocumentParser,
    BaseDocumentValidator,
    BaseLifecycleManager,
    BasePartyValidator,
    EInvoicingMCPServer,
)
from mcp_einvoicing_core.exceptions import (
    AuthenticationError,
    DocumentGenerationError,
    EInvoicingError,
    PartyValidationError,
    PlatformError,
    ValidationError,
    XSDValidationError,
)
from mcp_einvoicing_core.http_client import (
    AuthMode,
    BaseEInvoicingClient,
    OAuthConfig,
    TokenCache,
)
from mcp_einvoicing_core.models import (
    DocumentValidationResult,
    InvoiceDocument,
    InvoiceLineItem,
    InvoiceParty,
    PartyAddress,
    PaymentTerms,
    TaxIdentifier,
    VATSummary,
)
from mcp_einvoicing_core.xml_utils import (
    filter_empty_values,
    format_amount,
    format_error,
    format_quantity,
    validate_date_iso,
    validate_iban,
    xml_element,
    xml_optional,
)

__version__ = "0.1.0"

__all__ = [
    # Base classes
    "BaseDocumentGenerator",
    "BaseDocumentParser",
    "BaseDocumentValidator",
    "BaseLifecycleManager",
    "BasePartyValidator",
    "EInvoicingMCPServer",
    # Exceptions
    "EInvoicingError",
    "ValidationError",
    "PartyValidationError",
    "DocumentGenerationError",
    "XSDValidationError",
    "AuthenticationError",
    "PlatformError",
    # HTTP client
    "AuthMode",
    "BaseEInvoicingClient",
    "OAuthConfig",
    "TokenCache",
    # Models
    "TaxIdentifier",
    "PartyAddress",
    "InvoiceParty",
    "InvoiceLineItem",
    "VATSummary",
    "PaymentTerms",
    "InvoiceDocument",
    "DocumentValidationResult",
    # XML / format utilities
    "format_amount",
    "format_quantity",
    "validate_date_iso",
    "validate_iban",
    "xml_element",
    "xml_optional",
    "format_error",
    "filter_empty_values",
]
