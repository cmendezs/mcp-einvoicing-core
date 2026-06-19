# mcp-einvoicing-core

[English](README.md) | [Francais](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Espanol](README.es.md) | [Portugues (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Topics:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Paquet de base pour les serveurs MCP de facturation electronique.

Fournit des classes abstraites de base, des modeles Pydantic partages, des utilitaires XML et un client HTTP
afin que les paquets specifiques par pays (`mcp-facture-electronique-fr`, `mcp-fattura-elettronica-it`, `mcp-nfe-br`, ...)
partagent un socle commun sans dupliquer le code.

---

## Ce que ce paquet fournit

| Module | Contenu | Utilise par |
|--------|---------|-------------|
| `models.py` | `InvoiceParty`, `InvoiceLineItem`, `VATSummary`, `PaymentTerms`, `InvoiceDocument`, `DocumentValidationResult` | IT (generation structuree de factures), futur BE/PL/DE/ES |
| `base_server.py` | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `EInvoicingMCPServer` | Tous les adaptateurs pays |
| `xml_utils.py` | `format_amount`, `format_quantity`, `validate_date_iso`, `validate_iban`, `xml_element`, `xml_optional`, `format_error`, `filter_empty_values` | IT (extrait tel quel), futurs formats bases sur XML |
| `http_client.py` | `TokenCache`, `OAuthConfig`, `BaseEInvoicingClient` (OAuth2 + sans authentification) | FR (extrait tel quel), futurs pays bases sur API |
| `exceptions.py` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` | Tous les adaptateurs pays |
| `logging_utils.py` | `setup_logging`, `get_logger` | Tous les adaptateurs pays |

## Installation

```bash
pip install mcp-einvoicing-core
```

Ce paquet ne possede **aucune dependance specifique a un pays**. `lxml` (necessaire pour la validation XSD
en IT et dans les futurs pays) est declare par chaque paquet pays individuellement.

## Architecture

```
mcp-einvoicing-core           ← ce paquet
  ├── BaseDocumentGenerator   ← abstrait : generate(InvoiceDocument) → str
  ├── BaseDocumentValidator   ← abstrait : validate(xml) → DocumentValidationResult
  ├── BaseDocumentParser      ← abstrait : parse(xml) → dict
  ├── BaseLifecycleManager    ← abstrait : submit/search/get_status (HTTP asynchrone)
  ├── BasePartyValidator      ← abstrait : validate_seller/buyer/tax_id
  ├── BaseEInvoicingClient    ← concret : HTTP asynchrone + OAuth2/sans-auth/token
  ├── InvoiceDocument (Pydantic)  ← modele de donnees partage
  └── EInvoicingMCPServer     ← registre de plugins encapsulant FastMCP

mcp-facture-electronique-fr   ← adaptateur pays (FR)
  ├── PAConfig(OAuthConfig)
  ├── FlowClient(BaseEInvoicingClient)      ← OAuth2, XP Z12-013 Annexe A
  ├── DirectoryClient(BaseEInvoicingClient) ← OAuth2, XP Z12-013 Annexe B
  └── FrLifecycleManager(BaseLifecycleManager)

mcp-fattura-elettronica-it    ← adaptateur pays (IT)
  ├── ItalyPartyValidator(BasePartyValidator)   ← Partita IVA modulo-10
  ├── FatturaGenerator(BaseDocumentGenerator)   ← FatturaPA XML v1.6.1
  ├── FatturaValidator(BaseDocumentValidator)   ← lxml XSD v1.6.1
  └── FatturaParser(BaseDocumentParser)         ← lxml xpath
```

## Patron d'enregistrement de plugins

Les paquets pays enregistrent leurs outils sur une instance FastMCP partagee ou autonome :

```python
# Autonome (server.py existant, aucune modification necessaire)
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="…")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# Multi-pays (EInvoicingMCPServer optionnel)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="…")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

## Compatibilite Claude Desktop / Cursor / Kiro

Les configurations existantes pour `mcp-facture-electronique-fr` et `mcp-fattura-elettronica-it`
ne necessitent **aucune modification** : les noms d'outils, les signatures, les variables d'environnement
et les points d'entree (`server:main`) sont entierement preserves.

## Compatibilite avec la feuille de route

| Pays | Statut | Norme | Transport | Herite de | Redefinit | Lacunes connues |
|------|--------|-------|-----------|-----------|-----------|-----------------|
| [🇧🇪 BE](https://github.com/cmendezs/mcp-einvoicing-be) | ✅ Termine | Peppol BIS 3.0 | AS4 / Peppol | toutes les classes de base | `generate()` → UBL 2.1, `validate()` → Schematron EN16931 | Aucune |
| [🇫🇷 FR](https://github.com/cmendezs/mcp-facture-electronique-fr) | ✅ Termine | XP Z12-013 | Hybride / hub PPF | `BaseEInvoicingClient`, `BaseLifecycleManager` | `submit_lifecycle_status`, `healthcheck` | Aucune |
| [🇩🇪 DE](https://github.com/cmendezs/mcp-einvoicing-de) | ✅ Termine | ZUGFeRD / XRechnung | AS4 / Peppol | toutes les classes de base | `generate()` retourne des octets PDF (base64) | Type de retour de `generate()` : ambiguite `str` vs `bytes` |
| [🇮🇹 IT](https://github.com/cmendezs/mcp-fattura-elettronica-it) | ✅ Termine | FatturaPA v1.6.1 | Direct / SDI | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BasePartyValidator` | toutes les methodes abstraites | `to_invoice_document()` pas encore implemente |
| [🇵🇱 PL](https://github.com/cmendezs/mcp-ksef-pl) | ✅ Termine | KSeF FA(2) | API directe | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseLifecycleManager` | flux d'authentification KSeF | Mode d'authentification `MTLS` pas encore implemente |
| [🇪🇸 ES](https://github.com/cmendezs/mcp-facturacion-electronica-es) | ✅ Termine | FACeB2B / FacturaE | API directe | toutes les classes de base | authentification mTLS | Mode d'authentification `MTLS` pas encore implemente |
| [🇧🇷 BR](https://github.com/cmendezs/mcp-nfe-br) | 🚧 En cours | NF-e / NFC-e (schema 4.00) | API directe / SEFAZ | `BasePartyValidator` | validation CPF/CNPJ | Generation NF-e/NFC-e et integration SEFAZ prevues |
| 🇷🇴 RO | 📋 Backlog | RO-UBL (EN 16931) | API directe / clearance | `BaseDocumentGenerator`, `BaseLifecycleManager` | flux de clearance ANAF | Variante `BaseSchematronValidator` necessaire |
| 🇬🇷 GR | 📋 Backlog | myDATA XML | API directe / reporting | `BaseEInvoicingClient`, `BaseLifecycleManager` | flux d'authentification + reporting myDATA | Client API myDATA pas encore concu |
| 🇳🇱🇸🇪🇩🇰🇳🇴 Nordiques/NL | 📋 Backlog | Peppol BIS 3.0 / UBL | AS4 / Peppol | toutes les classes de base | `generate()` → UBL 2.1, `validate()` → Schematron | Reutilise la couche de transport AS4 de BE |
| 🇵🇹 PT | 📋 Backlog | CIUS-PT + QR Code | Signature / direct | `BaseDocumentGenerator`, `BaseDocumentValidator` | signature qualifiee + injection QR | Integration de la signature qualifiee pas encore concue |

## Notes architecturales

### Interface de transport

A mesure que le nombre d'adaptateurs augmente, une abstraction `TransportInterface` dans core evitera la duplication entre les pays partageant la meme couche de transport :

| Transport | Pays |
|-----------|------|
| **API directe** (clearance / reporting) | FR, RO, GR, HU |
| **AS4 / reseau Peppol** | BE, DE, Nordiques/NL |
| **Hybride / hub** | FR (double chemin PPF/PDP) |

### Allemagne : 80 % de reutilisation a partir de FR

Le mandat allemand (actif depuis janvier 2025 pour la reception B2B) favorise fortement ZUGFeRD/Factur-X, le meme modele XML embarque dans un PDF que le profil francais Factur-X. La logique de generation et de validation XML de `mcp-facture-electronique-fr` peut etre reutilisee avec des modifications minimales, faisant de DE l'adaptateur le moins couteux apres BE.

### ViDA / DRR (2030)

D'ici juillet 2030, tous les systemes nationaux devront s'aligner sur l'obligation de declaration numerique de l'UE (Digital Reporting Requirement) pour les transactions transfrontalieres. L'utilisation de **EN 16931** comme modele de donnees interne `InvoiceDocument` dans ce paquet de base prepare deja le projet pour l'avenir : les adaptateurs pays traduisent EN 16931 vers le format local, et non l'inverse.

## Licence

Apache 2.0, voir [LICENSE](LICENSE).
