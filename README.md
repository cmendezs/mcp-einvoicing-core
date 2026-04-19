# mcp-einvoicing-core

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

This package has **no country-specific dependencies**.  `lxml` (needed for XSD validation
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

## Roadmap compatibility

| Country | Standard | Inherits | Overrides | Known gaps |
|---------|----------|----------|-----------|------------|
| 🇫🇷 FR (existing) | XP Z12-013 | `BaseEInvoicingClient`, `BaseLifecycleManager` | `submit_lifecycle_status`, `healthcheck` | None |
| 🇮🇹 IT (existing) | FatturaPA v1.6.1 | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BasePartyValidator` | all abstract methods | `to_invoice_document()` not yet implemented |
| 🇧🇪 BE 2026 | Peppol BIS 3.0 | all base classes | `generate()` → UBL 2.1, `validate()` → Schematron EN16931 | Need `BaseSchematronValidator` variant |
| 🇵🇱 PL 2026 | KSeF FA(2) | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseLifecycleManager` | KSeF session auth flow | `MTLS` auth mode not yet implemented |
| 🇩🇪 DE | ZUGFeRD / XRechnung | all base classes | `generate()` returns PDF bytes (base64) | `generate()` return type: `str` vs `bytes` ambiguity |
| 🇪🇸 ES | FACeB2B / FacturaE | all base classes | mTLS auth | `MTLS` auth mode not yet implemented |

---

## Compatibilité Claude Desktop / Cursor / Kiro

Les packages pays existants (`mcp-facture-electronique-fr`, `mcp-fattura-elettronica-it`)
**ne nécessitent aucun changement** de configuration côté client. Les noms d'outils, signatures,
et points d'entrée (`server:main`) sont préservés à l'identique.

---

# mcp-einvoicing-core (FR)

Package de base pour les serveurs MCP de facturation électronique européenne.

Fournit les classes abstraites, les modèles Pydantic partagés, les utilitaires XML
et le client HTTP OAuth2 réutilisables par tous les adaptateurs pays.

## Ce que ce package apporte

- **Modèles partagés** : `InvoiceParty`, `InvoiceLineItem`, `VATSummary`, `PaymentTerms`,
  `InvoiceDocument` — représentent le concept de facture indépendamment du format pays.
- **Classes abstraites** : contrats d'interface clairs (ABC) pour la génération, validation,
  parsing, gestion du cycle de vie et validation des parties.
- **Client HTTP réutilisable** : `BaseEInvoicingClient` avec OAuth2 `client_credentials`,
  cache de token, retry automatique sur 401 — extrait verbatim de `mcp-facture-electronique-fr`.
- **Utilitaires XML** : `format_amount`, `validate_iban`, `xml_element`, `filter_empty_values` —
  extraits de `mcp-fattura-elettronica-it`.
- **Exceptions standardisées** : hiérarchie `EInvoicingError` commune à tous les adaptateurs.
- **Registre de plugins** : `EInvoicingMCPServer` permet de combiner plusieurs pays dans un
  seul serveur MCP sans modifier les `server.py` existants.

## Installation

```bash
pip install mcp-einvoicing-core
```

## Rétrocompatibilité

Les configurations Claude Desktop / Cursor / Kiro existantes pour `mcp-facture-electronique-fr`
et `mcp-fattura-elettronica-it` sont **entièrement préservées** : noms d'outils, signatures,
variables d'environnement, points d'entrée.

## Licence

Apache 2.0 — voir [LICENSE](LICENSE).
