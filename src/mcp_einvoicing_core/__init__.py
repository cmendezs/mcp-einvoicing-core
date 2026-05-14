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
    SubmitResult,
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
    BaseStructuredValidator,
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
from mcp_einvoicing_core.digital_signature import (
    BaseDocumentSigner,
    XAdESEPESSigner,
    XAdESSignerConfig,
)
from mcp_einvoicing_core.qr import generate_qr_png_base64
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP
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

from mcp_einvoicing_core.audit import (
    DEFAULT_CORE_MODULES,
    AuditReport,
    CheckFinding,
    CheckResult,
    SEVERITY_BLOCKING,
    SEVERITY_OK,
    SEVERITY_SKIP,
    SEVERITY_WARNING,
    make_report,
    parse_audit_args,
    render_summary_table,
    run_check_core_coverage,
    run_check_version_compatibility,
)

__version__ = "0.6.0"

__all__ = [
    # Base classes
    "BaseDocumentGenerator",
    "BaseDocumentParser",
    "BaseDocumentValidator",
    "BaseLifecycleManager",
    "BasePartyValidator",
    "EInvoicingMCPServer",
    "SubmitResult",
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
    # Structured document validation
    "BaseStructuredValidator",
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
    # Rounding constants (re-exported for convenience)
    "ROUND_HALF_UP",
    "ROUND_HALF_EVEN",
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
    # QR code generation
    "generate_qr_png_base64",
    # Document signing
    "BaseDocumentSigner",
    "XAdESSignerConfig",
    "XAdESEPESSigner",
    # Audit infrastructure (mcp-einvoicing-core[audit] optional extra)
    "DEFAULT_CORE_MODULES",
    "AuditReport",
    "CheckFinding",
    "CheckResult",
    "SEVERITY_BLOCKING",
    "SEVERITY_OK",
    "SEVERITY_SKIP",
    "SEVERITY_WARNING",
    "make_report",
    "parse_audit_args",
    "render_summary_table",
    "run_check_core_coverage",
    "run_check_version_compatibility",
]
