"""
mcp-einvoicing-core — Base package for European electronic invoicing MCP servers.

Provides abstract base classes, shared Pydantic models, XML utilities, an HTTP client
with OAuth2 support, and a plugin registry so country packages register their tools
without modifying the base server.

Country packages import from here and register via EInvoicingMCPServer.register_plugin().
"""

from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP

from mcp_einvoicing_core.archive import ArchiveMetadata, BaseArchiveProvider
from mcp_einvoicing_core.audit import (
    DEFAULT_CORE_MODULES,
    KNOWN_SHARED_HELPERS,
    SEVERITY_BLOCKING,
    SEVERITY_OK,
    SEVERITY_SKIP,
    SEVERITY_WARNING,
    AuditReport,
    CheckFinding,
    CheckResult,
    TaxRate,
    load_rates,
    make_report,
    parse_audit_args,
    render_summary_table,
    run_check_core_coverage,
    run_check_known_shared_helpers,
    run_check_version_compatibility,
)
from mcp_einvoicing_core.audit_log import AuditAction, AuditLog, get_audit_log
from mcp_einvoicing_core.base_server import (
    BaseDocumentGenerator,
    BaseDocumentParser,
    BaseDocumentValidator,
    BaseLifecycleManager,
    BasePartyValidator,
    EInvoicingMCPServer,
    SubmitResult,
    assert_not_read_only,
    scrub,
)
from mcp_einvoicing_core.confirmation import ConfirmationGate, ConfirmationStore
from mcp_einvoicing_core.convert import Syntax, convert_wire_format
from mcp_einvoicing_core.credit_note import BillingReference, EN16931CreditNote
from mcp_einvoicing_core.digital_signature import (
    BaseDocumentSigner,
    CAdESSigner,
    CAdESSignerConfig,
    XAdESEPESSigner,
    XAdESSignerConfig,
    XMLDSigSigner,
    XMLDSigSignerConfig,
    load_certificate_der,
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
from mcp_einvoicing_core.en16931_codelist_tools import register_en16931_codelist_tools
from mcp_einvoicing_core.endpoints import (
    BaseEnvironmentEndpoints,
    EndpointEnvironment,
    EndpointSet,
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
from mcp_einvoicing_core.http_client import (
    AuthMode,
    BaseEInvoicingClient,
    JWSConfig,
    OAuthConfig,
    OAuthValues,
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
    TaxIdValidationResult,
    VATSummary,
)
from mcp_einvoicing_core.pdf import CANONICAL_HYBRID_PDF_FILENAMES, PDFEmbedder
from mcp_einvoicing_core.pdf_tools import identify_and_extract_pdf, register_pdf_tools
from mcp_einvoicing_core.peppol import (
    PEPPOL_BIS_BILLING_30,
    PeppolEnvironment,
    PeppolLookupResult,
    PeppolParticipantId,
    PeppolServiceInfo,
    PeppolSMPClient,
    resolve_naptr,
)
from mcp_einvoicing_core.peppol.codelists import CodeList, CodelistNotConfiguredError
from mcp_einvoicing_core.peppol.directory import (
    PeppolBusinessCard,
    PeppolBusinessEntity,
    PeppolDirectoryClient,
    PeppolDirectoryContact,
    PeppolDirectoryDocType,
    PeppolDirectoryIdentifier,
    PeppolDirectoryName,
    PeppolDirectorySearchResult,
)
from mcp_einvoicing_core.peppol.mls import (
    MLS_CUSTOMIZATION_ID,
    MLS_PROFILE_ID,
    MessageLevelStatus,
    MLSDocumentReference,
    MLSDocumentResponse,
    MLSEndpoint,
    MLSLineReference,
    MLSLineResponse,
    MLSResponse,
    MLSStatus,
    build_mls,
    load_mls_codelist,
    mls_schematron_validator,
    parse_mls,
    validate_mls,
)
from mcp_einvoicing_core.peppol.mls_tools import register_peppol_mls_tools
from mcp_einvoicing_core.peppol.reporting import (
    EndUserStatisticsReport,
    EUSRFullSet,
    EUSRSubset,
    ReporterID,
    ReportHeader,
    ReportKey,
    ReportPeriod,
    TransactionStatisticsReport,
    TSRSubtotal,
    TSRTotal,
    load_eusr_codelist,
    load_tsr_codelist,
    parse_eusr,
    parse_tsr,
    peppol_reporting_validator,
    validate_eusr,
    validate_tsr,
)
from mcp_einvoicing_core.peppol.reporting_tools import register_peppol_reporting_tools
from mcp_einvoicing_core.peppol.tools import (
    IdentifierAdapter,
    default_id_adapter,
    register_peppol_tools,
)
from mcp_einvoicing_core.peppol.transport import (
    AS4Credentials,
    AS4InboundError,
    AS4InboundHandler,
    AS4InboundMessage,
    AS4MessageEnvelope,
    AS4Receipt,
    AS4ReceiptHandler,
    AS4SignatureVerificationResult,
    AS4TransportClient,
    MimeParseError,
    PeppolTransmitter,
    SBDHDocumentIdentification,
    SBDHIdentifier,
    SBDHScope,
    SignedAttachment,
    StandardBusinessDocumentHeader,
    build_error_envelope,
    build_receipt_envelope,
    parse_mime_multipart,
    sign_as4_message,
    verify_as4_signature,
)
from mcp_einvoicing_core.peppol.trust import (
    PeppolPKINotConfiguredError,
    PeppolTrustStore,
    RevocationCheckResult,
    check_revocation,
    validate_certificate_chain,
    verify_smp_signature,
)
from mcp_einvoicing_core.profile_registry import (
    ProfileEntry,
    ProfileRegistry,
    profile_registry,
    set_profile_registry,
)
from mcp_einvoicing_core.qr import generate_qr_png_base64
from mcp_einvoicing_core.routing import RoutingIdentifier, RoutingIdValidationResult
from mcp_einvoicing_core.schematron import (
    BaseJSONValidator,
    BaseStructuredValidator,
    BaseXSDValidator,
    SaxonSchematronValidator,
    SchematronValidator,
    ValidationMessage,
    ValidationResult,
    XSDValidator,
    get_xslt_version,
    load_schematron_validator,
)
from mcp_einvoicing_core.testing import InvoiceFixtureFactory
from mcp_einvoicing_core.ubl_documents import BaseUBLDocument
from mcp_einvoicing_core.wire_formats import (
    CII_NSMAP,
    UBL_NSMAP,
    EN16931CIIParser,
    EN16931CIISerializer,
    EN16931UBLParser,
    EN16931UBLSerializer,
)
from mcp_einvoicing_core.xml_utils import (
    filter_empty_values,
    format_amount,
    format_error,
    format_quantity,
    mark_untrusted,
    mark_untrusted_fields,
    resolve_xml_input,
    validate_date_iso,
    validate_iban,
    xml_element,
    xml_optional,
)

__version__ = "1.29.0"

__all__ = [
    # Archive provider
    "ArchiveMetadata",
    "BaseArchiveProvider",
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
    "OAuthValues",
    "OAuthConfig",
    "JWSConfig",
    "TokenCache",
    # Country-agnostic models
    "TaxIdentifier",
    "TaxIdValidationResult",
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
    "BaseXSDValidator",
    "BaseJSONValidator",
    "ValidationMessage",
    "ValidationResult",
    "SchematronValidator",
    "SaxonSchematronValidator",
    "XSDValidator",
    "get_xslt_version",
    "load_schematron_validator",
    # Peppol SMP client
    "PeppolEnvironment",
    "PeppolParticipantId",
    "PeppolServiceInfo",
    "PeppolLookupResult",
    "PeppolSMPClient",
    "PEPPOL_BIS_BILLING_30",
    "resolve_naptr",
    # Peppol tool plugin
    "register_peppol_tools",
    "default_id_adapter",
    "IdentifierAdapter",
    # Peppol eDEC code lists
    "CodeList",
    "CodelistNotConfiguredError",
    # EN 16931 semantic code lists
    "register_en16931_codelist_tools",
    # Peppol Directory search client
    "PeppolDirectoryClient",
    "PeppolDirectorySearchResult",
    "PeppolBusinessCard",
    "PeppolBusinessEntity",
    "PeppolDirectoryIdentifier",
    "PeppolDirectoryDocType",
    "PeppolDirectoryName",
    "PeppolDirectoryContact",
    # Peppol EUSR/TSR reporting
    "EndUserStatisticsReport",
    "EUSRFullSet",
    "EUSRSubset",
    "TransactionStatisticsReport",
    "TSRTotal",
    "TSRSubtotal",
    "ReportHeader",
    "ReportPeriod",
    "ReporterID",
    "ReportKey",
    "parse_eusr",
    "parse_tsr",
    "validate_eusr",
    "validate_tsr",
    "peppol_reporting_validator",
    "load_eusr_codelist",
    "load_tsr_codelist",
    "register_peppol_reporting_tools",
    # Peppol MLS (Message Level Status)
    "MessageLevelStatus",
    "MLSEndpoint",
    "MLSStatus",
    "MLSResponse",
    "MLSLineReference",
    "MLSLineResponse",
    "MLSDocumentReference",
    "MLSDocumentResponse",
    "MLS_CUSTOMIZATION_ID",
    "MLS_PROFILE_ID",
    "parse_mls",
    "validate_mls",
    "mls_schematron_validator",
    "build_mls",
    "load_mls_codelist",
    "register_peppol_mls_tools",
    # Peppol AS4 transport
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
    # Peppol PKI trust-store validation
    "PeppolTrustStore",
    "PeppolPKINotConfiguredError",
    "RevocationCheckResult",
    "validate_certificate_chain",
    "check_revocation",
    "verify_smp_signature",
    # Profile registry
    "ProfileEntry",
    "ProfileRegistry",
    "profile_registry",
    "set_profile_registry",
    # Test fixture factory
    "InvoiceFixtureFactory",
    # Non-invoice UBL document base (Peppol Ordering family, etc.)
    "BaseUBLDocument",
    # PDF/A-3 utilities
    "PDFEmbedder",
    "CANONICAL_HYBRID_PDF_FILENAMES",
    # Hybrid-PDF tool plugin
    "register_pdf_tools",
    "identify_and_extract_pdf",
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
    "mark_untrusted",
    "mark_untrusted_fields",
    # Output masking
    "scrub",
    # Read-only mode guard
    "assert_not_read_only",
    # Audit log
    "AuditAction",
    "AuditLog",
    "get_audit_log",
    # HITL confirmation gate
    "ConfirmationGate",
    "ConfirmationStore",
    # Wire format conversion
    "Syntax",
    "convert_wire_format",
    # EN 16931 credit note
    "BillingReference",
    "EN16931CreditNote",
    # Endpoint routing
    "BaseEnvironmentEndpoints",
    "EndpointEnvironment",
    "EndpointSet",
    # Routing identifier validators
    "RoutingIdentifier",
    "RoutingIdValidationResult",
    # EN 16931 wire formats (UBL 2.1 and CII)
    "EN16931UBLSerializer",
    "EN16931UBLParser",
    "EN16931CIISerializer",
    "EN16931CIIParser",
    "UBL_NSMAP",
    "CII_NSMAP",
    # QR code generation
    "generate_qr_png_base64",
    # Document signing
    "BaseDocumentSigner",
    "CAdESSignerConfig",
    "CAdESSigner",
    "XAdESSignerConfig",
    "XAdESEPESSigner",
    "XMLDSigSignerConfig",
    "XMLDSigSigner",
    "load_certificate_der",
    # Audit infrastructure (mcp-einvoicing-core[audit] optional extra)
    "DEFAULT_CORE_MODULES",
    "KNOWN_SHARED_HELPERS",
    "AuditReport",
    "CheckFinding",
    "CheckResult",
    "SEVERITY_BLOCKING",
    "SEVERITY_OK",
    "SEVERITY_SKIP",
    "SEVERITY_WARNING",
    "TaxRate",
    "load_rates",
    "make_report",
    "parse_audit_args",
    "render_summary_table",
    "run_check_core_coverage",
    "run_check_known_shared_helpers",
    "run_check_version_compatibility",
]
