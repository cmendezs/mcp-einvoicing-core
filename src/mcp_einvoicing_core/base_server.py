"""
Abstract base classes and plugin registry for mcp-einvoicing-core.

This module defines the interface contracts that all country adapters must fulfil.
Every abstract method has at least one concrete use from the existing FR and IT repos
(verified in Step 1 analysis).

Plugin pattern:
  The EInvoicingMCPServer wraps a FastMCP instance. Country packages call
  server.register_plugin(register_fn, "country-name") to add their tools.
  This preserves all existing tool names and signatures — the registration
  functions in FR (register_flow_tools, register_directory_tools) and IT
  (register_header_tools, register_body_tools, register_global_tools) are
  called unchanged.

[DECISION: EInvoicingMCPServer wraps FastMCP rather than subclassing it.]
  Rationale: FastMCP's tool registration API (@mcp.tool()) works as a decorator
  on the instance.  Subclassing would require relaying every FastMCP method or
  exposing the inner instance anyway.  The wrapper keeps the public API clean
  while providing the plugin registry.

[DECISION: Abstract base classes use ABC + abstractmethod rather than Protocol.]
  Rationale: Country adapters need to inherit shared behaviour (e.g. default
  to_invoice_document raises NotImplementedError with a helpful message), not just
  satisfy a structural type. ABC gives us that + is more explicit for junior devs.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Callable, Optional

from fastmcp import FastMCP

from mcp_einvoicing_core.models import (
    DocumentValidationResult,
    InvoiceDocument,
    InvoiceParty,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Document generation
# ---------------------------------------------------------------------------


class BaseDocumentGenerator(ABC):
    """Abstract document generator.

    Concrete use — IT:  generate_fattura_xml (assembles FatturaPA XML from structured data)
    Concrete use — FR:  (FR submits pre-built binary flows; in a future FR generator this
                         would produce Factur-X / UBL / CII documents from InvoiceDocument)
    Concrete use — DE:  ZUGFeRD COMFORT/EXTENDED XML generation
    Concrete use — BE:  UBL 2.1 Peppol BIS 3.0 XML generation
    """

    @abstractmethod
    def generate(self, document: InvoiceDocument) -> str:
        """Generate a country-specific document (XML string) from an InvoiceDocument.

        Returns:
            The generated document as a string (XML, or base64-encoded PDF for ZUGFeRD).

        [AMBIGUITY: ZUGFeRD returns a hybrid PDF (bytes), not a plain XML string.
         Option A: Return str always — ZUGFeRD adapter returns base64-encoded PDF.
         Option B: Return str | bytes — more honest, requires callers to handle both.
         Chosen: Option A for now (base64-encoded PDF as str). This keeps the return
         type clean. Flag as gap in Step 5.]
        """

    @abstractmethod
    def get_format_name(self) -> str:
        """Return the format name (e.g. 'FatturaPA', 'UBL-2.1', 'ZUGFeRD-EN16931').

        Used in MCP server instructions and tool descriptions.
        """

    @abstractmethod
    def get_country_code(self) -> str:
        """Return the ISO 3166-1 alpha-2 country code (e.g. 'IT', 'FR', 'DE').

        Used to route documents to the correct country adapter.
        """

    def get_namespace(self) -> Optional[str]:
        """Return the primary XML namespace for this format (optional).

        IT:  http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2
        UBL: urn:oasis:names:specification:ubl:schema:xsd:Invoice-2
        FR:  urn:xp-z12-013:lifecycle-status:1.0 (only for CDAR XML)

        Override in adapters that build XML with namespaces.
        """
        return None


# ---------------------------------------------------------------------------
# Document validation
# ---------------------------------------------------------------------------


class BaseDocumentValidator(ABC):
    """Abstract document validator.

    Concrete use — IT: validate_fattura_xsd (lxml XSD v1.6.1 + local xmldsig resolver)
    Concrete use — DE: ZUGFeRD/XRechnung Schematron + EN16931 CII validation
    Concrete use — BE: Peppol BIS 3.0 Schematron validation
    Concrete use — FR: (no local validation — AP validates on submission; a future
                        local pre-validator would inherit this class)
    """

    @abstractmethod
    def validate(self, document_content: str | bytes) -> DocumentValidationResult:
        """Validate a document against the country-specific schema.

        Args:
            document_content: XML string or bytes to validate.

        Returns:
            DocumentValidationResult with valid flag, errors, and metadata.
        """

    @abstractmethod
    def get_schema_version(self) -> str:
        """Return the schema/standard version used for validation.

        IT:  'FatturaPA v1.6.1'
        DE:  'ZUGFeRD 2.3 / EN16931'
        BE:  'Peppol BIS 3.0 / EN16931'
        """

    def get_schema_path(self) -> Optional[str]:
        """Return the local file path to the XSD/Schematron, if applicable.

        IT:  schemas/FatturaPA_v1.6.1.xsd (bundled in the IT package wheel)
        Override in adapters that ship their own schema files.
        """
        return None


# ---------------------------------------------------------------------------
# Document parsing
# ---------------------------------------------------------------------------


class BaseDocumentParser(ABC):
    """Abstract document parser.

    Concrete use — IT: parse_fattura_xml (lxml xpath extraction → structured dict)
                        export_to_json (dict → clean JSON)
    Concrete use — BE: UBL 2.1 XML → structured dict
    Concrete use — DE: ZUGFeRD CII XML → structured dict
    Concrete use — FR: (future) Factur-X / UBL → structured dict
    """

    @abstractmethod
    def parse(self, document_content: str | bytes) -> dict:
        """Parse a country-specific document to a structured Python dict.

        The dict structure is country-specific (preserves original field names).
        Use to_invoice_document() to obtain a normalized InvoiceDocument.

        Args:
            document_content: XML string or bytes.

        Returns:
            A dict mirroring the source document's structure.
        """

    def to_invoice_document(self, parsed: dict) -> InvoiceDocument:
        """Convert a parsed dict to a normalized InvoiceDocument.

        Default implementation raises NotImplementedError with guidance.
        Country adapters that support bidirectional conversion override this.

        IT v0.1.0 does not implement this (parse_fattura_xml only goes one way).
        [AMBIGUITY: IT parse_fattura_xml returns a country-specific dict, not an
         InvoiceDocument.  Adding this conversion layer is recommended for v0.2.
         Option A: Implement in IT adapter → clean roundtrip (generate → validate → parse → InvoiceDocument).
         Option B: Leave as-is → parse returns the IT-specific dict only.
         Both options are valid for v0.1.0.  Override in v0.2 adapter.]
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement to_invoice_document(). "
            "Override this method in the country adapter to enable roundtrip conversion."
        )


# ---------------------------------------------------------------------------
# Lifecycle / platform management
# ---------------------------------------------------------------------------


class BaseLifecycleManager(ABC):
    """Abstract lifecycle manager for national e-invoicing platforms.

    Concrete use — FR: FlowClient (submit_flow, search_flows, get_flow,
                        submit_lifecycle_status, healthcheck)
    Concrete use — BE: Peppol AS4 document submission (B2B/B2G)
    Concrete use — PL: KSeF API (submit, check status, fetch UPO receipt)
    Concrete use — IT: (out of scope v0.1.0 — no direct SDI submission yet)
    Concrete use — ES: FACeB2B API (submit, check status)
    """

    @abstractmethod
    async def submit_document(self, document: bytes | str, metadata: dict) -> dict:
        """Submit a document to the national platform.

        FR: POST /v1/flows (multipart: file + flowInfo JSON)
        PL: POST /api/online/Send/Invoice (KSeF — requires prior session token)
        BE: AS4 message via Peppol Access Point

        Args:
            document: The binary or text document to submit.
            metadata: Platform-specific metadata (flowSyntax, processingRule, etc.)

        Returns:
            Platform response dict (flowId/status in FR, sessionToken in PL, etc.)
        """

    @abstractmethod
    async def get_document_status(self, document_id: str) -> dict:
        """Get the status of a previously submitted document.

        FR:  GET /v1/flows/{flowId}?docType=Metadata
        PL:  GET /api/online/Invoice/Status/{invoiceElementReference}
        """

    @abstractmethod
    async def search_documents(self, criteria: dict) -> dict:
        """Search for submitted documents by criteria.

        FR: POST /v1/flows/search (processingRule, flowType, status, updatedAfter)
        PL: POST /api/online/Query/Invoice/Sync
        """

    async def submit_lifecycle_status(
        self,
        document_id: str,
        status: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Submit a lifecycle status update (Approved, Refused, Cashed, etc.).

        FR: Builds CDAR XML and submits via POST /v1/flows (flowSyntax='CDAR').
        IT: (no direct platform submission in v0.1.0 — local only)
        PL: Status is implicitly tracked by KSeF; no separate submission.

        Default raises NotImplementedError — override only for platforms that
        require explicit status reporting (FR, ES, BE B2G).
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support explicit lifecycle status submission."
        )

    async def healthcheck(self) -> dict:
        """Check platform availability.

        FR: GET /v1/healthcheck → {"status": "ok" | "degraded" | "unavailable"}
        Default returns a stub — override where the platform exposes a healthcheck.
        """
        return {"status": "not_implemented", "note": "No healthcheck endpoint configured"}


# ---------------------------------------------------------------------------
# Party validation
# ---------------------------------------------------------------------------


class BasePartyValidator(ABC):
    """Abstract party validator (seller and buyer).

    Concrete use — IT: validate_cedente_prestatore (seller: Partita IVA + RegimeFiscale)
                        validate_cessionario (buyer: IdFiscaleIVA or CodiceFiscale)
    Concrete use — FR: (future) validate SIREN/SIRET against PPF directory
    Concrete use — DE: validate USt-IdNr (DE+9 digits) via VIES or local
    Concrete use — BE: validate BTW-nummer (BE+10 digits) via VIES
    Concrete use — PL: validate NIP (10 digits, checksum)
    Concrete use — ES: validate NIF (9 chars: letter+7 digits+letter)
    """

    @abstractmethod
    def validate_seller(self, **kwargs) -> dict:
        """Validate a seller party for the country's e-invoicing system.

        Args:
            **kwargs: Country-specific fields (id_paese, id_codice, denominazione,
                      regime_fiscale for IT; siren, name, platform_id for FR; etc.)

        Returns:
            A validated seller block dict on success, or {"error": "..."} on failure.
        """

    @abstractmethod
    def validate_buyer(self, **kwargs) -> dict:
        """Validate a buyer party for the country's e-invoicing system.

        Args:
            **kwargs: Country-specific fields.

        Returns:
            A validated buyer block dict on success, or {"error": "..."} on failure.
        """

    @abstractmethod
    def validate_tax_id(self, tax_id: str, country_code: str) -> dict:
        """Validate a tax identifier format and checksum.

        IT:  validate_partita_iva — 11 digits, modulo-10 checksum
        PL:  validate_nip — 10 digits, weighted checksum
        ES:  validate_nif — 9 chars, letter+digit validation
        DE:  validate_ust_idnr — DE+9 digits, VIES format check

        Args:
            tax_id:       The raw identifier string (no spaces, no country prefix).
            country_code: ISO 3166-1 alpha-2 country code.

        Returns:
            {"valid": bool, "value": cleaned_str} or {"valid": False, "error": "..."}
        """

    def validate_party(self, party: InvoiceParty) -> list[str]:
        """Validate a normalized InvoiceParty and return a list of error strings.

        Default implementation performs generic cross-field checks.
        Country adapters override for country-specific rules.
        """
        errors: list[str] = []
        if not party.name and not (party.first_name and party.last_name):
            errors.append("Party must have either a name or first_name + last_name.")
        if not party.tax_id.identifier:
            errors.append("Tax identifier is empty.")
        return errors


# ---------------------------------------------------------------------------
# Plugin registry and MCP server wrapper
# ---------------------------------------------------------------------------


ToolRegistrationFn = Callable[[FastMCP], None]
"""Type alias for a country adapter's tool registration function.

Example:
    def register_flow_tools(mcp: FastMCP) -> None:
        @mcp.tool()
        async def submit_flow(...) -> dict: ...
"""


class EInvoicingMCPServer:
    """MCP server wrapper with plugin registry for country adapters.

    Each country package calls register_plugin() with its own registration
    function.  The underlying FastMCP instance is shared, so all tools appear
    in a single MCP server namespace.

    Usage:
        # In a multi-country server (e.g. mcp-einvoicing-eu):
        server = EInvoicingMCPServer(
            name="mcp-einvoicing-eu",
            instructions="Multi-country European e-invoicing MCP server.",
        )
        from mcp_fattura_elettronica_it.tools.header_tools import register_header_tools
        server.register_plugin(register_header_tools, "it-header")
        server.run()

        # Country packages can also use their own standalone FastMCP instance
        # (backward-compatible — no change required to existing server.py files).

    [DECISION: Country packages are not forced to use EInvoicingMCPServer.]
    FR and IT currently create a bare FastMCP in their server.py.  They can continue
    to do so.  EInvoicingMCPServer is an optional convenience for scenarios where
    multiple countries run in a single process.
    """

    def __init__(
        self,
        name: str,
        instructions: str = "",
        log_level: int = logging.INFO,
    ) -> None:
        self.mcp = FastMCP(name=name, instructions=instructions)
        self._plugins: list[str] = []
        self._log_level = log_level
        logger.setLevel(log_level)

    def register_plugin(self, registration_fn: ToolRegistrationFn, plugin_name: str) -> None:
        """Register a country adapter's tools on the shared MCP instance.

        Args:
            registration_fn: A function that takes a FastMCP instance and calls
                             @mcp.tool() on it (e.g. register_flow_tools, register_header_tools).
            plugin_name:     Human-readable label for logging/diagnostics.
        """
        registration_fn(self.mcp)
        self._plugins.append(plugin_name)
        logger.info("Plugin registered: %s", plugin_name)

    def run(self) -> None:
        """Start the MCP server in stdio mode."""
        logger.info(
            "Starting EInvoicingMCPServer '%s' with plugins: %s",
            self.mcp.name,
            ", ".join(self._plugins) if self._plugins else "(none)",
        )
        self.mcp.run()

    @property
    def registered_plugins(self) -> list[str]:
        """Return the list of registered plugin names."""
        return list(self._plugins)

    @property
    def plugin_count(self) -> int:
        """Return the number of registered plugins."""
        return len(self._plugins)
