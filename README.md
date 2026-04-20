# mcp-einvoicing-core

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)

**Topics:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `european-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `xml` `base-library`

Base package for European electronic invoicing MCP servers.

Provides abstract base classes, shared Pydantic models, XML utilities, and an HTTP client
so country-specific packages (`mcp-facture-electronique-fr`, `mcp-fattura-elettronica-it`, …)
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

| Country | Status | Standard | Transport | Inherits | Overrides | Known gaps |
|---------|--------|----------|-----------|----------|-----------|------------|
| [🇫🇷 FR](https://github.com/cmendezs/mcp-facture-electronique-fr) | ✅ Done | XP Z12-013 | Hybrid / PPF hub | `BaseEInvoicingClient`, `BaseLifecycleManager` | `submit_lifecycle_status`, `healthcheck` | None |
| [🇮🇹 IT](https://github.com/cmendezs/mcp-fattura-elettronica-it) | ✅ Done | FatturaPA v1.6.1 | Direct / SDI | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BasePartyValidator` | all abstract methods | `to_invoice_document()` not yet implemented |
| [🇧🇪 BE](https://github.com/cmendezs/mcp-einvoicing-be) | ✅ Done | Peppol BIS 3.0 | AS4 / Peppol | all base classes | `generate()` → UBL 2.1, `validate()` → Schematron EN16931 | None |
| 🇵🇱 PL | 🔄 In progress | KSeF FA(2) | Direct API | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseLifecycleManager` | KSeF session auth flow | `MTLS` auth mode not yet implemented |
| 🇩🇪 DE | 🔄 In progress | ZUGFeRD / XRechnung | AS4 / Peppol | all base classes | `generate()` returns PDF bytes (base64) | `generate()` return type: `str` vs `bytes` ambiguity |
| 🇪🇸 ES | 🔄 In progress | FACeB2B / FacturaE | Direct API | all base classes | mTLS auth | `MTLS` auth mode not yet implemented |
| 🇷🇴 RO | 📋 Backlog | RO-UBL (EN 16931) | Direct API / clearance | `BaseDocumentGenerator`, `BaseLifecycleManager` | ANAF clearance flow | `BaseSchematronValidator` variant needed |
| 🇬🇷 GR | 📋 Backlog | myDATA XML | Direct API / reporting | `BaseEInvoicingClient`, `BaseLifecycleManager` | myDATA auth + reporting flow | myDATA API client not yet designed |
| 🇳🇱🇸🇪🇩🇰🇳🇴 Nordics/NL | 📋 Backlog | Peppol BIS 3.0 / UBL | AS4 / Peppol | all base classes | `generate()` → UBL 2.1, `validate()` → Schematron | Reuses BE AS4 transport layer |
| 🇵🇹 PT | 📋 Backlog | CIUS-PT + QR Code | Signature / direct | `BaseDocumentGenerator`, `BaseDocumentValidator` | Qualified signature + QR injection | Qualified signature integration not designed |

## Architectural notes

### Transport interface

As the adapter count grows, a `TransportInterface` abstraction in core will prevent duplication across countries that share the same transport layer:

| Transport | Countries |
|-----------|-----------|
| **Direct API** (clearance / reporting) | FR, RO, GR, HU |
| **AS4 / Peppol network** | BE, DE, Nordics/NL |
| **Hybrid / hub** | FR (PPF/PDP dual path) |

### Germany: 80% reuse from FR

Germany's mandate (active since Jan 2025 for B2B receiving) heavily favors ZUGFeRD/Factur-X — the same PDF-embedded XML model as the French Factur-X profile. The `mcp-facture-electronique-fr` XML generation and validation logic can be reused with minimal changes, making DE the lowest-effort next adapter after BE.

### ViDA / DRR (2030)

By July 2030, all national systems must align with the EU Digital Reporting Requirement for cross-border transactions. Using **EN 16931** as the internal `InvoiceDocument` data model in this core package already future-proofs the project: country adapters translate EN 16931 → local format, not the other way around.

## License

Apache 2.0 — see [LICENSE](LICENSE).
