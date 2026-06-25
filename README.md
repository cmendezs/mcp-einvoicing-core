# mcp-einvoicing-core

[English](README.md) | [Francais](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Espanol](README.es.md) | [Portugues (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Topics:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Base package for electronic invoicing MCP servers.

Provides shared Pydantic models, EN 16931 invoice tree, UBL/CII wire format serializers,
an OAuth2 HTTP client, Peppol SMP lookup, digital signature primitives, and a compliance
audit framework so country-specific packages share a common foundation without duplicating code.

---

## What this package provides

| Module | Contents |
|--------|----------|
| `models` | `InvoiceDocument`, `InvoiceParty`, `InvoiceLineItem`, `PartyAddress`, `VATSummary`, `PaymentTerms`, `DocumentValidationResult`, `TaxIdentifier` (per-country tax ID validators: IT, FR, DE, BE, ES, PL, BR), `TaxIdValidationResult` |
| `en16931` | `EN16931Invoice`, `EN16931Party`, `EN16931LineItem`, `EN16931Address`, `EN16931Tax`, `EN16931AllowanceCharge`, `EN16931PaymentMeans` |
| `credit_note` | `EN16931CreditNote` (type codes 381/383/384/385), `BillingReference` |
| `wire_formats` | `EN16931UBLSerializer`, `EN16931UBLParser`, `EN16931CIISerializer`, `EN16931CIIParser`, `UBL_NSMAP`, `CII_NSMAP` |
| `convert` | `Syntax` (UBL, CII), `convert_wire_format` (auto-detect source, serialize to target) |
| `base_server` | `EInvoicingMCPServer`, `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `SubmitResult`, `assert_not_read_only`, `scrub` |
| `http_client` | `BaseEInvoicingClient` (OAuth2, mTLS, bearer, API key, none), `OAuthConfig`, `OAuthValues`, `TokenCache`, `AuthMode` |
| `peppol` | `PeppolSMPClient`, `PeppolParticipantId`, `PeppolServiceInfo`, `PeppolLookupResult`, `PeppolEnvironment`, `PEPPOL_BIS_BILLING_30` |
| `peppol.transport` | `AS4MessageEnvelope`, `AS4TransportClient`, `AS4ReceiptHandler`, `PeppolTransmitter`, `AS4Receipt`, `AS4Credentials` (Peppol AS4 outbound transmission) |
| `schematron` | `SchematronValidator`, `BaseStructuredValidator`, `BaseXSDValidator`, `BaseJSONValidator`, `ValidationMessage`, `ValidationResult` |
| `digital_signature` | `BaseDocumentSigner`, `XAdESEPESSigner`, `XAdESSignerConfig`, `XMLDSigSigner`, `XMLDSigSignerConfig` |
| `endpoints` | `BaseEnvironmentEndpoints`, `EndpointSet`, `EndpointEnvironment` (sandbox/production URL routing) |
| `routing` | `RoutingIdentifier` (static validators: `validate_de_leitweg`), `RoutingIdValidationResult` |
| `profile_registry` | `ProfileEntry`, `ProfileRegistry`, `profile_registry`, `set_profile_registry` |
| `pdf` | `PDFEmbedder` (PDF/A-3 XML embedding) |
| `qr` | `generate_qr_png_base64` |
| `xml_utils` | `format_amount`, `format_quantity`, `xml_element`, `xml_optional`, `validate_date_iso`, `validate_iban`, `resolve_xml_input`, `mark_untrusted`, `mark_untrusted_fields`, `filter_empty_values`, `format_error` |
| `download_rules` | `DownloadSpec`, `download_artefacts` |
| `testing` | `InvoiceFixtureFactory` (shared pytest fixtures) |
| `audit_log` | `AuditLog`, `AuditAction`, `get_audit_log` |
| `confirmation` | `ConfirmationGate`, `ConfirmationStore` (human-in-the-loop gate) |
| `exceptions` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `SchematronValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` |
| `logging_utils` | `setup_logging`, `get_logger` |
| `audit` | Compliance audit framework: `AuditReport`, `CheckResult`, `CheckFinding`, severity constants, `make_report`, `render_summary_table`, `parse_audit_args`, `run_check_core_coverage`, `run_check_version_compatibility`, `run_check_known_shared_helpers`, `TaxRate`, `load_rates` (optional `[audit]` extra) |

## Installation

```bash
pip install mcp-einvoicing-core
```

For the compliance audit framework (used by country package CI):

```bash
pip install mcp-einvoicing-core[audit]
```

## Architecture

Country packages subclass the core abstractions and register their tools on a shared or standalone MCP server:

```
mcp-einvoicing-core
  ├── EN16931Invoice / InvoiceDocument  ← canonical invoice models
  ├── EN16931CreditNote                 ← credit note (type codes 381/383/384/385)
  ├── EN16931UBL/CII Serializer/Parser  ← wire format round-trip
  ├── convert_wire_format               ← CII ↔ UBL conversion
  ├── BaseDocumentGenerator/Validator/Parser/LifecycleManager
  ├── BaseEInvoicingClient              ← async HTTP (OAuth2/mTLS/bearer/API key)
  ├── PeppolSMPClient                   ← participant lookup via SMP/SML
  ├── PeppolTransmitter                 ← AS4 outbound transmission
  ├── BaseDocumentSigner                ← XAdES-EPES / XMLDSig
  ├── BaseEnvironmentEndpoints          ← sandbox/production URL routing
  ├── RoutingIdentifier                 ← country-specific routing ID validation
  ├── EInvoicingMCPServer               ← plugin registry wrapping FastMCP
  └── Audit framework                   ← per-package compliance checks
```

## Country packages

| Country | Package | Standard |
|---------|---------|----------|
| France | [`mcp-facture-electronique-fr`](https://github.com/cmendezs/mcp-facture-electronique-fr) | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII |
| Germany | [`mcp-einvoicing-de`](https://github.com/cmendezs/mcp-einvoicing-de) | ZUGFeRD 2.x / XRechnung 3.x |
| Belgium | [`mcp-einvoicing-be`](https://github.com/cmendezs/mcp-einvoicing-be) | Peppol BIS 3.0 / PINT-BE |
| Italy | [`mcp-fattura-elettronica-it`](https://github.com/cmendezs/mcp-fattura-elettronica-it) | FatturaPA / SDI |
| Poland | [`mcp-ksef-pl`](https://github.com/cmendezs/mcp-ksef-pl) | KSeF FA(3) / FA(2) / Peppol BIS 3.0 |
| Spain | [`mcp-facturacion-electronica-es`](https://github.com/cmendezs/mcp-facturacion-electronica-es) | Factura-e / VeriFactu / SII / FACe |
| Brazil | [`mcp-nfe-br`](https://github.com/cmendezs/mcp-nfe-br) | NF-e / NFC-e (modelo 55/65, schema 4.00) / NFS-e Nacional |

## Plugin registration pattern

Country packages register their tools on a shared or standalone FastMCP instance:

```python
# Standalone
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="...")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# Multi-country (optional EInvoicingMCPServer)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="...")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

## Claude Desktop / Cursor / Kiro compatibility

Existing configurations for country packages require **no changes**: tool names,
signatures, environment variables, and entry points (`server:main`) are fully preserved.

## License

Apache 2.0 -- see [LICENSE](LICENSE).
