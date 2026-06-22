# mcp-einvoicing-core

[English](README.md) | [Francais](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Espanol](README.es.md) | [Portugues (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Topics:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Base package for electronic invoicing MCP servers.

Provides abstract base classes, shared Pydantic models, XML utilities, and an HTTP client
so country-specific packages (`mcp-facture-electronique-fr`, `mcp-fattura-elettronica-it`, `mcp-nfe-br`, …)
share a common foundation without duplicating code.

---

## What this package provides

| Module | Contents | Used by |
|--------|----------|---------|
| `models.py` | `InvoiceParty`, `InvoiceLineItem`, `VATSummary`, `PaymentTerms`, `InvoiceDocument`, `DocumentValidationResult` | IT (structured invoice generation), future BE/PL/DE/ES |
| `base_server.py` | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `EInvoicingMCPServer` | All country adapters |
| `xml_utils.py` | `format_amount`, `format_quantity`, `validate_date_iso`, `validate_iban`, `xml_element`, `xml_optional`, `format_error`, `filter_empty_values` | IT (extracted verbatim), future XML-based formats |
| `http_client.py` | `TokenCache`, `OAuthConfig`, `BaseEInvoicingClient` (OAuth2 + no-auth) | FR (extracted verbatim), future API-based countries |
| `exceptions.py` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` | All country adapters |
| `logging_utils.py` | `setup_logging`, `get_logger` | All country adapters |

## Installation

```bash
pip install mcp-einvoicing-core
```

This package has **no country-specific dependencies**. `lxml` (needed for XSD validation
in IT and future countries) is declared by each country package individually.

## Architecture

```
mcp-einvoicing-core           ← this package
  ├── BaseDocumentGenerator   ← abstract: generate(InvoiceDocument) → str
  ├── BaseDocumentValidator   ← abstract: validate(xml) → DocumentValidationResult
  ├── BaseDocumentParser      ← abstract: parse(xml) → dict
  ├── BaseLifecycleManager    ← abstract: submit/search/get_status (async HTTP)
  ├── BasePartyValidator      ← abstract: validate_seller/buyer/tax_id
  ├── BaseEInvoicingClient    ← concrete: async HTTP + OAuth2/no-auth/token
  ├── InvoiceDocument (Pydantic)  ← shared data model
  └── EInvoicingMCPServer     ← plugin registry wrapping FastMCP

mcp-facture-electronique-fr   ← country adapter (FR)
  ├── PAConfig(OAuthConfig)
  ├── FlowClient(BaseEInvoicingClient)      ← OAuth2, XP Z12-013 Annex A
  ├── DirectoryClient(BaseEInvoicingClient) ← OAuth2, XP Z12-013 Annex B
  └── FrLifecycleManager(BaseLifecycleManager)

mcp-fattura-elettronica-it    ← country adapter (IT)
  ├── ItalyPartyValidator(BasePartyValidator)   ← Partita IVA modulo-10
  ├── FatturaGenerator(BaseDocumentGenerator)   ← FatturaPA XML v1.6.1
  ├── FatturaValidator(BaseDocumentValidator)   ← lxml XSD v1.6.1
  └── FatturaParser(BaseDocumentParser)         ← lxml xpath
```

## Plugin registration pattern

Country packages register their tools on a shared or standalone FastMCP instance:

```python
# Standalone (existing server.py — no changes required)
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="…")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# Multi-country (optional EInvoicingMCPServer)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="…")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

## Claude Desktop / Cursor / Kiro compatibility

Existing configurations for `mcp-facture-electronique-fr` and `mcp-fattura-elettronica-it`
require **no changes**: tool names, signatures, environment variables, and entry points
(`server:main`) are fully preserved.

## Roadmap compatibility

Open backlog and sprint planning per country is in [`context-library/roadmap-2026.md`](../context-library/roadmap-2026.md). The table below reflects the canonical EN 16931 vs non-EN 16931 invoice pathway split (see `CLAUDE.md`).

| Country | Version | Standard | Invoice pathway | Transport |
|---------|---------|----------|-----------------|-----------|
| [🇧🇪 BE](https://github.com/cmendezs/mcp-einvoicing-be) | v0.2.0 published | Peppol BIS 3.0 / PINT-BE | `BEInvoice(EN16931Invoice)` | Peppol network (AS4) |
| [🇫🇷 FR](https://github.com/cmendezs/mcp-facture-electronique-fr) | v0.4.0 published | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | `EN16931Invoice` (target — see FR-SC-1) | Hybrid / PPF + PDP |
| [🇩🇪 DE](https://github.com/cmendezs/mcp-einvoicing-de) | v0.3.1 published | ZUGFeRD 2.x / XRechnung 3.x | `ZUGFeRDInvoice(EN16931Invoice)` | Direct + Peppol participant lookup |
| [🇮🇹 IT](https://github.com/cmendezs/mcp-fattura-elettronica-it) | v0.2.5 published | FatturaPA v1.2.x | EN 16931 (IT CIUS) | Direct / SdI |
| [🇵🇱 PL](https://github.com/cmendezs/mcp-ksef-pl) | v0.2.2 published | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | `KSeFInvoice(EN16931Invoice)` | Direct API + Peppol |
| [🇪🇸 ES](https://github.com/cmendezs/mcp-facturacion-electronica-es) | v0.2.0 published | Factura-e / VeriFactu / SII / FACe | Dual: `EN16931Invoice` (Factura-e) + `InvoiceDocument` (VeriFactu, SII) | Direct API (mTLS / OAuth2) |
| [🇧🇷 BR](https://github.com/cmendezs/mcp-nfe-br) | v0.5.2 published | NF-e / NFC-e (modelo 55/65, schema 4.00); NFS-e Nacional v1.01 | `BRInvoice(InvoiceDocument)` + `NFSeDocument(InvoiceDocument)` | Direct mTLS / SEFAZ + Gov.br OAuth2 / ADN |

Countries on the planning radar (not yet scaffolded — see [`roadmap-2026.md`](../context-library/roadmap-2026.md) "New country packages" section): IN, MX, RO, CO, CL, PE, VN, EG, HU, GR, KR, ID, EC, UY (Category 1 — fully live clearance); SG, MY, SA, NG, IL, PY, PH (Category 2 — rolling out in 2026); UAE, OM, SK, PT, DK, ZA (Category 3 — transition or late 2026/2027). Voluntary EU/APAC/NA jurisdictions are Category 4.

## Architectural notes

### Transport interface

As the adapter count grows, a `TransportInterface` abstraction in core will prevent duplication across countries that share the same transport layer. Current adapter coverage:

| Transport | Countries |
|-----------|-----------|
| **Direct API** (clearance / reporting / B2G) | FR (Chorus Pro + PDP/PPF), ES (AEAT + FACe), PL (KSeF), IT (SdI planned) |
| **mTLS to government webservice** | BR (SEFAZ), ES (VeriFactu, SII) |
| **Peppol network (AS4)** | BE, DE (planned via DE-PEPPOL-1, v0.5.0) |
| **OAuth2 to gov hub** | BR (Gov.br ADN for NFS-e Nacional) |

A dedicated `TransportInterface` is tracked as architectural work; today each country adapter extends `BaseEInvoicingClient` directly with the auth mode it needs (`AuthMode.OAUTH2_CLIENT_CREDENTIALS`, `AuthMode.MTLS`, `AuthMode.BEARER_TOKEN`, `AuthMode.NONE`).

### EN 16931 wire formats

Core ships `EN16931UBLSerializer`/`EN16931UBLParser` and `EN16931CIISerializer`/`EN16931CIIParser` (since v1.3.0) so EU country adapters do not reimplement UBL 2.1 or CII D16B serialisation. New EU country packages should extend these rather than write a parallel XML stack.

### ViDA / DRR (2030)

By July 2030, all national systems must align with the EU Digital Reporting Requirements (DRR) for cross-border transactions. Using **EN 16931** as the canonical EU invoice root (`EN16931Invoice`) already future-proofs the invoice-envelope side: country adapters translate `EN16931Invoice` to the local wire format, not the other way around. The DRR submission lifecycle itself (real-time structured transaction data submission to a central EU register, transaction ID issuance, cross-border 4-corner reconciliation) is not modelled in core today and is tracked as a separate workstream in [`roadmap-2026.md`](../context-library/roadmap-2026.md); do not equate "supports EN 16931 / Peppol" with "supports ViDA DRR".

## License

Apache 2.0 — see [LICENSE](LICENSE).
