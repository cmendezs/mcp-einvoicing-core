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
| `models` | `InvoiceDocument`, `InvoiceParty`, `InvoiceLineItem`, `PartyAddress`, `VATSummary`, `PaymentTerms`, `DocumentValidationResult`, `TaxIdentifier` (per-country tax ID validators: IT, FR, DE, BE, ES, PL, BR, AE, SG), `TaxIdValidationResult` |
| `en16931` | `EN16931Invoice`, `EN16931Party`, `EN16931LineItem`, `EN16931Address`, `EN16931Tax`, `EN16931AllowanceCharge`, `EN16931PaymentMeans` |
| `credit_note` | `EN16931CreditNote` (type codes 381/383/384/385), `BillingReference` |
| `ubl_documents` | `BaseUBLDocument` — shared envelope for non-invoice UBL/Peppol document families (Peppol Ordering, jurisdiction extensions); explicitly outside the `InvoiceDocument`/`EN16931Invoice` tree |
| `wire_formats` | `EN16931UBLSerializer`, `EN16931UBLParser`, `EN16931CIISerializer`, `EN16931CIIParser`, `UBL_NSMAP`, `CII_NSMAP` |
| `convert` | `Syntax` (UBL, CII), `convert_wire_format` (auto-detect source, serialize to target) |
| `base_server` | `EInvoicingMCPServer`, `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `SubmitResult`, `assert_not_read_only`, `scrub` |
| `http_client` | `BaseEInvoicingClient` (OAuth2, mTLS, bearer, API key, JWS, none), `OAuthConfig`, `OAuthValues`, `JWSConfig`, `TokenCache`, `AuthMode` |
| `peppol` | `PeppolSMPClient`, `PeppolParticipantId`, `PeppolServiceInfo`, `PeppolLookupResult`, `PeppolEnvironment`, `PEPPOL_BIS_BILLING_30`, `resolve_naptr` (standalone U-NAPTR/SML DNS diagnostic) |
| `peppol.tools` | `register_peppol_tools` (mountable FastMCP plugin: participant lookup, service endpoint, DNS diagnostic, AS4 send, Directory search, plus 8 eDEC code list tools), `default_id_adapter`, `IdentifierAdapter` (national identifier adapter contract) |
| `peppol.codelists` | `CodeList`, `CodelistNotConfiguredError`, `load_codelist` and the eDEC lookup functions (document types, processes, participant ID schemes, transport profiles, SPIS use cases). Requires `EINVOICING_PEPPOL_CODELIST_DIR`, see Configuration below |
| `genericode` | `parse_genericode`, `CodeList`, `CodelistNotConfiguredError` — shared OASIS Genericode 1.0 parser (used by `peppol.codelists` and `en16931_codelists`) |
| `en16931_codelists` | `en16931_codelist_tools.register_en16931_codelist_tools` (mountable FastMCP plugin: country, currency, ICD, UNCL1001/1153/4461/5305, allowance/item/charge reason, MIME, EAS, VATEX lookup). Requires `EINVOICING_EN16931_CODELIST_DIR`, see Configuration below |
| `peppol.directory` | `PeppolDirectoryClient` (public Peppol Directory REST search, no auth), `PeppolDirectorySearchResult`, `PeppolBusinessCard`, `PeppolBusinessEntity` |
| `peppol.transport` | `AS4MessageEnvelope`, `AS4TransportClient`, `AS4ReceiptHandler`, `PeppolTransmitter`, `AS4Receipt`, `AS4Credentials` (Peppol AS4 outbound transmission, now with real WS-Security message signing); `AS4InboundHandler`, `AS4InboundMessage`, `AS4InboundError`, `StandardBusinessDocumentHeader` (AS4 inbound receiver, C3 role); `sign_as4_message`, `verify_as4_signature` (WS-Security primitives) |
| `peppol.trust` | `PeppolTrustStore`, `validate_certificate_chain`, `check_revocation`, `verify_smp_signature` — OpenPeppol PKI chain/revocation/signature validation. Requires `EINVOICING_PEPPOL_PKI_DIR` (root certs not yet published by OpenPeppol as of this release — logic-only until supplied) |
| `peppol.reporting` | `parse_eusr`, `parse_tsr`, `validate_eusr`, `validate_tsr` — Peppol EUSR/TSR service-provider statistics report models and validation (bundled XSD + Schematron, optional `[xslt2]` extra) |
| `peppol.mls` | `parse_mls`, `validate_mls`, `build_mls` — Peppol Message Level Status (MLS) model and validation (bundled Schematron, optional `[xslt2]` extra) |
| `schematron` | `SchematronValidator` (XSLT 1.0), `SaxonSchematronValidator` (XSLT 2.0/3.0, optional `[xslt2]` extra), `load_schematron_validator` (auto-dispatch factory), `get_xslt_version`, `BaseStructuredValidator`, `BaseXSDValidator`, `XSDValidator` (generic concrete XSD validator), `BaseJSONValidator`, `ValidationMessage`, `ValidationResult` |
| `schematron_artifacts` | `en16931_base_schematron_validator` (bundled, compiled CEN EN16931 base Schematron — `BR-*` rules only, no Peppol overlay; optional `[xslt2]` extra) |
| `digital_signature` | `BaseDocumentSigner`, `XAdESEPESSigner`, `XAdESSignerConfig`, `XMLDSigSigner`, `XMLDSigSignerConfig`, `load_certificate_der` |
| `endpoints` | `BaseEnvironmentEndpoints`, `EndpointSet`, `EndpointEnvironment` (sandbox/production URL routing) |
| `routing` | `RoutingIdentifier` (static validators: `validate_de_leitweg`), `RoutingIdValidationResult` |
| `profile_registry` | `ProfileEntry`, `ProfileRegistry`, `profile_registry`, `set_profile_registry` |
| `pdf` | `PDFEmbedder` (PDF/A-3 XML embedding); `extract(filename=None)` tries canonical Factur-X/XRechnung/ZUGFeRD filenames in turn, `identify()` reads XMP to detect a hybrid PDF and its conformance level |
| `pdf_tools` | `register_pdf_tools` (mountable FastMCP plugin: `identify_and_extract_pdf`), `identify_and_extract_pdf` |
| `qr` | `generate_qr_png_base64` |
| `xml_utils` | `format_amount`, `format_quantity`, `xml_element`, `xml_optional`, `validate_date_iso`, `validate_iban`, `resolve_xml_input`, `mark_untrusted`, `mark_untrusted_fields`, `filter_empty_values`, `format_error` |
| `download_rules` | `DownloadSpec`, `download_artefacts` |
| `testing` | `InvoiceFixtureFactory` (shared pytest fixtures) |
| `audit_log` | `AuditLog`, `AuditAction`, `get_audit_log` |
| `confirmation` | `ConfirmationGate`, `ConfirmationStore` (human-in-the-loop gate) |
| `exceptions` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `SchematronValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` |
| `logging_utils` | `setup_logging`, `get_logger` |
| `audit` | Compliance audit framework: `AuditReport`, `CheckResult`, `CheckFinding`, severity constants, `make_report`, `render_summary_table`, `parse_audit_args`, `run_check_core_coverage`, `run_check_version_compatibility`, `run_check_known_shared_helpers`, `TaxRate`, `load_rates` (optional `[audit]` extra) |

## Country packages

| Country | Package | Standard | Scope | Coverage status |
|---------|---------|----------|-------|------------------|
| 🇧🇪 Belgium | [`mcp-einvoicing-be`](https://github.com/cmendezs/mcp-einvoicing-be) | Peppol BIS 3.0 / PINT-BE | B2B, 1 January 2026 | Live; Peppol-specific overlay rules not checked (EN 16931 base only) |
| 🇧🇷 Brazil | [`mcp-nfe-br`](https://github.com/cmendezs/mcp-nfe-br) | NF-e / NFC-e (modelo 55/65, schema 4.00) / NFS-e Nacional | B2B (NF-e) + B2C (NFC-e), both mandatory since 2008 | Live; IBS/CBS tax reform rollout ongoing through 2033 |
| 🇫🇷 France | [`mcp-facture-electronique-fr`](https://github.com/cmendezs/mcp-facture-electronique-fr) | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | B2B, phased rollout from 1 September 2026 | Live |
| 🇩🇪 Germany | [`mcp-einvoicing-de`](https://github.com/cmendezs/mcp-einvoicing-de) | ZUGFeRD 2.x / XRechnung 3.x | B2B, phased 2025 to 2028 | Live |
| 🇮🇹 Italy | [`mcp-fattura-elettronica-it`](https://github.com/cmendezs/mcp-fattura-elettronica-it) | FatturaPA / SDI | B2G + B2B + B2C, mandatory since 2019 (B2G since 2014) | Live |
| 🇵🇱 Poland | [`mcp-ksef-pl`](https://github.com/cmendezs/mcp-ksef-pl) | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | B2B, phased February 2026 to January 2027 | Live; batch session flow not implemented |
| 🇸🇬 Singapore | [`mcp-invoicenow-sg`](https://github.com/cmendezs/mcp-invoicenow-sg) | PINT-SG v1.4.1 / SG Peppol BIS Billing 3.0 | B2B, mandatory for GST-registered businesses from April 2026 | Live; validation scope limited to IRAS C5 acceptance checks, PINT-SG jurisdiction Schematron and EN 16931 base validation not yet wired |
| 🇪🇸 Spain | [`mcp-facturacion-electronica-es`](https://github.com/cmendezs/mcp-facturacion-electronica-es) | Factura-e / VeriFactu / SII / FACe | Pending Orden Ministerial, targeted 2026-10-01 | Live for VeriFactu/SII; B2B format wiring blocked on pending Orden Ministerial |
| 🇦🇪 United Arab Emirates | [`mcp-einvoicing-ae`](https://github.com/cmendezs/mcp-einvoicing-ae) | PINT AE (billing + self-billing) / Peppol AE TDD | B2B + B2G, voluntary pilot from July 2026, mandatory for large taxpayers from January 2027 | Live; validates CEN EN16931 base Schematron only, PINT AE jurisdiction overlay and TDD validation not yet available |

## Installation

```bash
pip install mcp-einvoicing-core
```

For the compliance audit framework (used by country package CI):

```bash
pip install mcp-einvoicing-core[audit]
```

For XSLT 2.0/3.0 Schematron validation (`SaxonSchematronValidator` — needed for Schematron
rule sets using XPath 2.0+ constructs, e.g. FNFE-MPE Factur-X 1.08 / ZUGFeRD):

```bash
pip install mcp-einvoicing-core[xslt2]
```

## Configuration

| Variable | Used by | Purpose |
|---|---|---|
| `EINVOICING_PEPPOL_CODELIST_DIR` | `peppol.codelists` (and the `peppol.tools` codelist tools) | Local directory containing your own copy of the OpenPeppol eDEC Code Lists. **Not bundled with this package**: the eDEC Code Lists carry no confirmed redistribution grant from OpenPeppol, so core ships only the parser and lookup tools, never the data itself. Download the "as GeneriCode" export for each artifact (Document Types, Participant Identifier Schemes, Processes, Transport Profiles, SPIS Use Case) from [docs.peppol.eu/edelivery/codelists](https://docs.peppol.eu/edelivery/codelists/index.html) and point this variable at the directory containing them. Filenames are matched by prefix, so a version bump (e.g. v9.7 to v9.8) needs no code change. Without this set, the codelist tools return a `configured: false` result with setup instructions rather than raising. |
| `EINVOICING_EN16931_CODELIST_DIR` | `en16931_codelists` (and its FastMCP tools) | Local directory containing your own copy of the CEF EN 16931 semantic code lists (country, currency, ICD, UNCL1001/1153/4461/5305, allowance/item/charge reason, MIME, EAS, VATEX). **Not bundled**, same posture as the eDEC lists above — download the "as GeneriCode" export bundle from the CEF EN 16931 code lists page. Filenames match exactly (`Country.gc`, not a version-prefixed name). Without this set, tools return `configured: false`. |
| `EINVOICING_PEPPOL_PKI_DIR` | `peppol.trust` | Local directory with `test/` and `prod/` subdirectories of PEM-encoded OpenPeppol PKI root/intermediate CA certificates, for AS4 message signature and SMP response signature chain validation. Not yet published by OpenPeppol as bundled data anywhere — trust functions report `trust_anchors_configured: false` until this is set. |
| `EINVOICING_SMP_ALLOWLIST` | `peppol` (`PeppolSMPClient`, `resolve_naptr`) | Comma-separated hostname suffixes to extend the built-in Peppol Access Point allowlist used when validating a resolved SMP hostname. |

## Architecture

Country packages subclass the core abstractions and register their tools on a shared or standalone MCP server:

```
mcp-einvoicing-core
  ├── EN16931Invoice / InvoiceDocument  ← canonical invoice models
  ├── EN16931CreditNote                 ← credit note (type codes 381/383/384/385)
  ├── EN16931UBL/CII Serializer/Parser  ← wire format round-trip
  ├── convert_wire_format               ← CII ↔ UBL conversion
  ├── BaseDocumentGenerator/Validator/Parser/LifecycleManager
  ├── BaseEInvoicingClient              ← async HTTP (OAuth2/mTLS/bearer/API key/JWS)
  ├── PeppolSMPClient                   ← participant lookup via SMP/SML
  ├── PeppolTransmitter                 ← AS4 outbound transmission
  ├── BaseDocumentSigner                ← XAdES-EPES / XMLDSig
  ├── BaseEnvironmentEndpoints          ← sandbox/production URL routing
  ├── RoutingIdentifier                 ← country-specific routing ID validation
  ├── EInvoicingMCPServer               ← plugin registry wrapping FastMCP
  └── Audit framework                   ← per-package compliance checks
```

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

Core also ships its own mountable Peppol tool plugin so country packages stop reimplementing
SMP lookup and AS4 send. Supply a national identifier adapter (a small function that normalizes
a bare national number, e.g. a VAT number, into a Peppol `"<scheme>:<value>"` participant ID):

```python
from mcp_einvoicing_core.peppol.tools import register_peppol_tools

def be_id_adapter(identifier: str) -> str:
    if ":" in identifier:
        return identifier
    return f"0208:{normalize_vat_be(identifier)[2:]}"  # KBO/BCE scheme

server.register_plugin(
    lambda m: register_peppol_tools(m, id_adapter=be_id_adapter), "peppol"
)
```

This registers `peppol_lookup_participant`, `peppol_get_service_endpoint`, `resolve_peppol_dns`,
`peppol_send`, `peppol_directory_search`, and 8 OpenPeppol eDEC code list tools (see Configuration
above for `EINVOICING_PEPPOL_CODELIST_DIR`, required for the code list tools). Separate mountable
plugins cover the EN 16931 semantic code lists (`en16931_codelist_tools.register_en16931_codelist_tools`),
Peppol reporting (`peppol.reporting_tools.register_peppol_reporting_tools`), and MLS
(`peppol.mls_tools.register_peppol_mls_tools`).

## Claude Desktop / Cursor / Kiro compatibility

Existing configurations for country packages require **no changes**: tool names,
signatures, environment variables, and entry points (`server:main`) are fully preserved.

## License

Apache 2.0 -- see [LICENSE](LICENSE).
