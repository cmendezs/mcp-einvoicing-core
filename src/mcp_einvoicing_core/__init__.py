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
from mcp_einvoicing_core.download_rules import DownloadSpec, download_artefacts
from mcp_einvoicing_core.en16931 import (
    EN16931Address,
    EN16931AllowanceCharge,
    EN16931Invoice,
    EN16931LineItem,
    EN16931Party,
    EN16931PaymentMeans,
    EN16931Tax,
)
from mcp_einvoicing_core.exceptions import (
    AuthenticationError,
    DocumentGenerationError,
    EInvoicingError,
    PartyValidationError,
    PlatformError,
    SchematronValidationError,
    ValidationError,
    XSDValidationError,
)
from mcp_einvoicing_core.peppol import (
    PEPPOL_BIS_BILLING_30,
    PeppolEnvironment,
    PeppolLookupResult,
    PeppolParticipantId,
    PeppolServiceInfo,
    PeppolSMPClient,
)
from mcp_einvoicing_core.schematron import (
    SchematronValidator,
    ValidationMessage,
    ValidationResult,
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
from mcp_einvoicing_core.pdf import PDFEmbedder
from mcp_einvoicing_core.profile_registry import ProfileEntry, ProfileRegistry, profile_registry
from mcp_einvoicing_core.testing import InvoiceFixtureFactory
from mcp_einvoicing_core.xml_utils import (
    filter_empty_values,
    format_amount,
    format_error,
    format_quantity,
    resolve_xml_input,
    validate_date_iso,
    validate_iban,
    xml_element,
    xml_optional,
)

__version__ = "0.3.0"

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
    "SchematronValidationError",
    "AuthenticationError",
    "PlatformError",
    # HTTP client
    "AuthMode",
    "BaseEInvoicingClient",
    "OAuthConfig",
    "TokenCache",
    # Country-agnostic models
    "TaxIdentifier",
    "PartyAddress",
    "InvoiceParty",
    "InvoiceLineItem",
    "VATSummary",
    "PaymentTerms",
    "InvoiceDocument",
    "DocumentValidationResult",
    # EN 16931 base models
    "EN16931Address",
    "EN16931Party",
    "EN16931Tax",
    "EN16931AllowanceCharge",
    "EN16931LineItem",
    "EN16931PaymentMeans",
    "EN16931Invoice",
    # Schematron validation
    "ValidationMessage",
    "ValidationResult",
    "SchematronValidator",
    # Peppol SMP client
    "PeppolEnvironment",
    "PeppolParticipantId",
    "PeppolServiceInfo",
    "PeppolLookupResult",
    "PeppolSMPClient",
    "PEPPOL_BIS_BILLING_30",
    # Profile registry
    "ProfileEntry",
    "ProfileRegistry",
    "profile_registry",
    # Test fixture factory
    "InvoiceFixtureFactory",
    # PDF/A-3 utilities
    "PDFEmbedder",
    # Download-rules framework
    "DownloadSpec",
    "download_artefacts",
    # XML / format utilities
    "format_amount",
    "format_quantity",
    "validate_date_iso",
    "validate_iban",
    "xml_element",
    "xml_optional",
    "format_error",
    "filter_empty_values",
    "resolve_xml_input",
]
