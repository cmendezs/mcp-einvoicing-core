# mcp-einvoicing-core

[English](README.md) | [Francais](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Espanol](README.es.md) | [Portugues (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Topics:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Basispaket fuer MCP-Server zur elektronischen Rechnungsstellung.

Stellt gemeinsame Pydantic-Modelle, einen EN-16931-Rechnungsbaum, UBL/CII-Serialisierer,
einen OAuth2-HTTP-Client, Peppol-SMP-Lookup, digitale Signaturprimitive und ein
Compliance-Audit-Framework bereit, damit laenderspezifische Pakete auf einer gemeinsamen
Grundlage aufbauen, ohne Code zu duplizieren.

---

## Was dieses Paket bereitstellt

| Modul | Inhalt |
|-------|--------|
| `models` | `InvoiceDocument`, `InvoiceParty`, `InvoiceLineItem`, `PartyAddress`, `VATSummary`, `PaymentTerms`, `DocumentValidationResult`, `TaxIdentifier` (laenderspezifische Steuer-ID-Validatoren: IT, FR, DE, BE, ES, PL, BR), `TaxIdValidationResult` |
| `en16931` | `EN16931Invoice`, `EN16931Party`, `EN16931LineItem`, `EN16931Address`, `EN16931Tax`, `EN16931AllowanceCharge`, `EN16931PaymentMeans` |
| `credit_note` | `EN16931CreditNote` (Typecodes 381/383/384/385), `BillingReference` |
| `wire_formats` | `EN16931UBLSerializer`, `EN16931UBLParser`, `EN16931CIISerializer`, `EN16931CIIParser`, `UBL_NSMAP`, `CII_NSMAP` |
| `convert` | `Syntax` (UBL, CII), `convert_wire_format` (automatische Quellerkennung, Serialisierung ins Zielformat) |
| `base_server` | `EInvoicingMCPServer`, `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `SubmitResult`, `assert_not_read_only`, `scrub` |
| `http_client` | `BaseEInvoicingClient` (OAuth2, mTLS, Bearer, API-Key, ohne), `OAuthConfig`, `OAuthValues`, `TokenCache`, `AuthMode` |
| `peppol` | `PeppolSMPClient`, `PeppolParticipantId`, `PeppolServiceInfo`, `PeppolLookupResult`, `PeppolEnvironment`, `PEPPOL_BIS_BILLING_30` |
| `schematron` | `SchematronValidator`, `BaseStructuredValidator`, `BaseXSDValidator`, `BaseJSONValidator`, `ValidationMessage`, `ValidationResult` |
| `digital_signature` | `BaseDocumentSigner`, `XAdESEPESSigner`, `XAdESSignerConfig`, `XMLDSigSigner`, `XMLDSigSignerConfig` |
| `endpoints` | `BaseEnvironmentEndpoints`, `EndpointSet`, `EndpointEnvironment` (Sandbox-/Produktions-URL-Routing) |
| `routing` | `RoutingIdentifier` (statische Validatoren: `validate_de_leitweg`), `RoutingIdValidationResult` |
| `profile_registry` | `ProfileEntry`, `ProfileRegistry`, `profile_registry`, `set_profile_registry` |
| `pdf` | `PDFEmbedder` (XML-Einbettung in PDF/A-3) |
| `qr` | `generate_qr_png_base64` |
| `xml_utils` | `format_amount`, `format_quantity`, `xml_element`, `xml_optional`, `validate_date_iso`, `validate_iban`, `resolve_xml_input`, `mark_untrusted`, `mark_untrusted_fields`, `filter_empty_values`, `format_error` |
| `download_rules` | `DownloadSpec`, `download_artefacts` |
| `testing` | `InvoiceFixtureFactory` (gemeinsame pytest-Fixtures) |
| `audit_log` | `AuditLog`, `AuditAction`, `get_audit_log` |
| `confirmation` | `ConfirmationGate`, `ConfirmationStore` (Human-in-the-Loop-Gate) |
| `exceptions` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `SchematronValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` |
| `logging_utils` | `setup_logging`, `get_logger` |
| `audit` | Compliance-Audit-Framework: `AuditReport`, `CheckResult`, `CheckFinding`, Severity-Konstanten, `make_report`, `render_summary_table`, `parse_audit_args`, `run_check_core_coverage`, `run_check_version_compatibility`, `run_check_known_shared_helpers`, `TaxRate`, `load_rates` (optionales Extra `[audit]`) |

## Installation

```bash
pip install mcp-einvoicing-core
```

Fuer das Compliance-Audit-Framework (von der CI der Laenderpakete verwendet):

```bash
pip install mcp-einvoicing-core[audit]
```

## Architektur

Laenderpakete erben von den Core-Abstraktionen und registrieren ihre Tools auf einem gemeinsamen oder eigenstaendigen MCP-Server:

```
mcp-einvoicing-core
  ├── EN16931Invoice / InvoiceDocument  ← kanonische Rechnungsmodelle
  ├── EN16931CreditNote                 ← Gutschrift (Typecodes 381/383/384/385)
  ├── EN16931UBL/CII Serializer/Parser  ← Wire-Format-Roundtrip
  ├── convert_wire_format               ← CII ↔ UBL-Konvertierung
  ├── BaseDocumentGenerator/Validator/Parser/LifecycleManager
  ├── BaseEInvoicingClient              ← async HTTP (OAuth2/mTLS/Bearer/API-Key)
  ├── PeppolSMPClient                   ← Teilnehmer-Lookup ueber SMP/SML
  ├── BaseDocumentSigner                ← XAdES-EPES / XMLDSig
  ├── BaseEnvironmentEndpoints          ← Sandbox-/Produktions-URL-Routing
  ├── RoutingIdentifier                 ← laenderspezifische Routing-ID-Validierung
  ├── EInvoicingMCPServer               ← Plugin-Registry ueber FastMCP
  └── Audit-Framework                   ← Compliance-Pruefungen pro Paket
```

## Laenderpakete

| Land | Paket | Standard |
|------|-------|----------|
| Frankreich | [`mcp-facture-electronique-fr`](https://github.com/cmendezs/mcp-facture-electronique-fr) | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII |
| Deutschland | [`mcp-einvoicing-de`](https://github.com/cmendezs/mcp-einvoicing-de) | ZUGFeRD 2.x / XRechnung 3.x |
| Belgien | [`mcp-einvoicing-be`](https://github.com/cmendezs/mcp-einvoicing-be) | Peppol BIS 3.0 / PINT-BE |
| Italien | [`mcp-fattura-elettronica-it`](https://github.com/cmendezs/mcp-fattura-elettronica-it) | FatturaPA / SDI |
| Polen | [`mcp-ksef-pl`](https://github.com/cmendezs/mcp-ksef-pl) | KSeF FA(3) / FA(2) / Peppol BIS 3.0 |
| Spanien | [`mcp-facturacion-electronica-es`](https://github.com/cmendezs/mcp-facturacion-electronica-es) | Factura-e / VeriFactu / SII / FACe |
| Brasilien | [`mcp-nfe-br`](https://github.com/cmendezs/mcp-nfe-br) | NF-e / NFC-e (modelo 55/65, schema 4.00) / NFS-e Nacional |

## Plugin-Registrierungsmuster

Laenderpakete registrieren ihre Tools auf einer gemeinsamen oder eigenstaendigen FastMCP-Instanz:

```python
# Eigenstaendig
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="...")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# Multi-Laender (optionaler EInvoicingMCPServer)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="...")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

## Kompatibilitaet mit Claude Desktop / Cursor / Kiro

Bestehende Konfigurationen fuer Laenderpakete erfordern **keine Aenderungen**:
Tool-Namen, Signaturen, Umgebungsvariablen und Einstiegspunkte (`server:main`)
bleiben vollstaendig erhalten.

## Lizenz

Apache 2.0, siehe [LICENSE](LICENSE).
