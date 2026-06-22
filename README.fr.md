# mcp-einvoicing-core

[English](README.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Topics:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Paquet de base pour les serveurs MCP de facturation électronique.

Fournit des classes abstraites de base, des modèles Pydantic partagés, des utilitaires XML et un client HTTP
afin que les paquets spécifiques par pays (`mcp-facture-electronique-fr`, `mcp-fattura-elettronica-it`, `mcp-nfe-br`, ...)
partagent un socle commun sans dupliquer le code.

---

## Ce que ce paquet fournit

| Module | Contenu | Utilisé par |
|--------|---------|-------------|
| `models.py` | `InvoiceParty`, `InvoiceLineItem`, `VATSummary`, `PaymentTerms`, `InvoiceDocument`, `DocumentValidationResult` | IT (génération structurée de factures), futur BE/PL/DE/ES |
| `base_server.py` | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `EInvoicingMCPServer` | Tous les adaptateurs pays |
| `xml_utils.py` | `format_amount`, `format_quantity`, `validate_date_iso`, `validate_iban`, `xml_element`, `xml_optional`, `format_error`, `filter_empty_values` | IT (extrait tel quel), futurs formats basés sur XML |
| `http_client.py` | `TokenCache`, `OAuthConfig`, `BaseEInvoicingClient` (OAuth2 + sans authentification) | FR (extrait tel quel), futurs pays basés sur API |
| `exceptions.py` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` | Tous les paquets pays |
| `logging_utils.py` | `setup_logging`, `get_logger` | Tous les paquets pays |

## Installation

```bash
pip install mcp-einvoicing-core
```

Ce paquet ne possède **aucune dépendance spécifique à un pays**. `lxml` (nécessaire pour la validation XSD
en IT et dans les futurs pays) est déclaré par chaque paquet pays individuellement.

## Architecture

```
mcp-einvoicing-core           ← ce paquet
  ├── BaseDocumentGenerator   ← abstrait : generate(InvoiceDocument) → str
  ├── BaseDocumentValidator   ← abstrait : validate(xml) → DocumentValidationResult
  ├── BaseDocumentParser      ← abstrait : parse(xml) → dict
  ├── BaseLifecycleManager    ← abstrait : submit/search/get_status (HTTP asynchrone)
  ├── BasePartyValidator      ← abstrait : validate_seller/buyer/tax_id
  ├── BaseEInvoicingClient    ← concret : HTTP asynchrone + OAuth2/sans-auth/token
  ├── InvoiceDocument (Pydantic)  ← modèle de données partagé
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

Les paquets pays enregistrent leurs outils sur une instance FastMCP partagée ou autonome :

```python
# Autonome (server.py existant, aucune modification nécessaire)
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

## Compatibilité Claude Desktop / Cursor / Kiro

Les configurations existantes pour `mcp-facture-electronique-fr` et `mcp-fattura-elettronica-it`
ne nécessitent **aucune modification** : les noms d'outils, les signatures, les variables d'environnement
et les points d'entrée (`server:main`) sont entièrement préservés.

## Compatibilité avec la feuille de route

Le backlog ouvert et la planification des sprints par pays sont dans [`context-library/roadmap-2026.md`](../context-library/roadmap-2026.md). Le tableau ci-dessous reflète la séparation canonique des arbres de facture EN 16931 et hors EN 16931 (voir `CLAUDE.md`).

| Pays | Version | Norme | Arbre de facture | Transport |
|------|---------|-------|------------------|-----------|
| [🇧🇪 BE](https://github.com/cmendezs/mcp-einvoicing-be) | v0.2.0 publié | Peppol BIS 3.0 / PINT-BE | `BEInvoice(EN16931Invoice)` | Réseau Peppol (AS4) |
| [🇫🇷 FR](https://github.com/cmendezs/mcp-facture-electronique-fr) | v0.4.0 publié | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | `EN16931Invoice` (cible — voir FR-SC-1) | Hybride / PPF + PDP |
| [🇩🇪 DE](https://github.com/cmendezs/mcp-einvoicing-de) | v0.3.1 publié | ZUGFeRD 2.x / XRechnung 3.x | `ZUGFeRDInvoice(EN16931Invoice)` | Direct + lookup de participant Peppol |
| [🇮🇹 IT](https://github.com/cmendezs/mcp-fattura-elettronica-it) | v0.2.5 publié | FatturaPA v1.2.x | EN 16931 (CIUS italien) | Direct / SdI |
| [🇵🇱 PL](https://github.com/cmendezs/mcp-ksef-pl) | v0.2.2 publié | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | `KSeFInvoice(EN16931Invoice)` | API directe + Peppol |
| [🇪🇸 ES](https://github.com/cmendezs/mcp-facturacion-electronica-es) | v0.2.0 publié | Factura-e / VeriFactu / SII / FACe | Double : `EN16931Invoice` (Factura-e) + `InvoiceDocument` (VeriFactu, SII) | API directe (mTLS / OAuth2) |
| [🇧🇷 BR](https://github.com/cmendezs/mcp-nfe-br) | v0.5.2 publié | NF-e / NFC-e (modelo 55/65, schéma 4.00) ; NFS-e Nacional v1.01 | `BRInvoice(InvoiceDocument)` + `NFSeDocument(InvoiceDocument)` | mTLS direct / SEFAZ + Gov.br OAuth2 / ADN |

Pays sur le radar de planification (non encore scaffoldés — voir la section "New country packages" de [`roadmap-2026.md`](../context-library/roadmap-2026.md)) : IN, MX, RO, CO, CL, PE, VN, EG, HU, GR, KR, ID, EC, UY (catégorie 1 — clearance entièrement en service) ; SG, MY, SA, NG, IL, PY, PH (catégorie 2 — déploiement en 2026) ; UAE, OM, SK, PT, DK, ZA (catégorie 3 — transition ou fin 2026/2027). Les juridictions UE/APAC/AN volontaires relèvent de la catégorie 4.

## Notes architecturales

### Interface de transport

À mesure que le nombre d'adaptateurs augmente, une abstraction `TransportInterface` dans core évitera la duplication entre les pays partageant la même couche de transport. Couverture actuelle des adaptateurs :

| Transport | Pays |
|-----------|------|
| **API directe** (clearance / reporting / B2G) | FR (Chorus Pro + PDP/PPF), ES (AEAT + FACe), PL (KSeF), IT (SdI prévu) |
| **mTLS vers webservice gouvernemental** | BR (SEFAZ), ES (VeriFactu, SII) |
| **Réseau Peppol (AS4)** | BE, DE (prévu via DE-PEPPOL-1, v0.5.0) |
| **OAuth2 vers hub gouvernemental** | BR (Gov.br ADN pour NFS-e Nacional) |

Une `TransportInterface` dédiée est suivie en tant que travail architectural ; aujourd'hui chaque adaptateur pays étend directement `BaseEInvoicingClient` avec le mode d'authentification dont il a besoin (`AuthMode.OAUTH2_CLIENT_CREDENTIALS`, `AuthMode.MTLS`, `AuthMode.BEARER_TOKEN`, `AuthMode.NONE`).

### Formats filaires EN 16931

Le paquet de base fournit `EN16931UBLSerializer`/`EN16931UBLParser` et `EN16931CIISerializer`/`EN16931CIIParser` (depuis la v1.3.0) pour que les adaptateurs UE ne réimplémentent pas la sérialisation UBL 2.1 ou CII D16B. Les nouveaux paquets pays UE doivent étendre ces classes plutôt qu'écrire une pile XML parallèle.

### ViDA / DRR (2030)

D'ici juillet 2030, tous les systèmes nationaux devront s'aligner sur les Digital Reporting Requirements (DRR) de l'UE pour les transactions transfrontalières. L'utilisation de **EN 16931** comme racine canonique de facture UE (`EN16931Invoice`) prépare déjà le côté enveloppe de facture pour l'avenir : les adaptateurs pays traduisent `EN16931Invoice` vers le format filaire local, et non l'inverse. Le cycle de vie de soumission DRR lui-même (transmission en temps réel de données de transaction structurées vers un registre central UE, émission d'identifiants de transaction, réconciliation 4 coins transfrontalière) n'est pas modélisé dans le core actuellement et est suivi comme un workstream séparé dans [`roadmap-2026.md`](../context-library/roadmap-2026.md) ; ne pas confondre "supporte EN 16931 / Peppol" et "supporte ViDA DRR".

## Autres serveurs MCP de facturation électronique

| Pays | Serveur |
|---------|--------|
| 🌍 Global | [mcp-einvoicing-core](https://github.com/cmendezs/mcp-einvoicing-core) |
| 🇧🇪 Belgique | [mcp-einvoicing-be](https://github.com/cmendezs/mcp-einvoicing-be) |
| 🇧🇷 Brésil | [mcp-nfe-br](https://github.com/cmendezs/mcp-nfe-br) |
| 🇫🇷 France | [mcp-facture-electronique-fr](https://github.com/cmendezs/mcp-facture-electronique-fr) |
| 🇩🇪 Allemagne | [mcp-einvoicing-de](https://github.com/cmendezs/mcp-einvoicing-de) |
| 🇮🇹 Italie | [mcp-fattura-elettronica-it](https://github.com/cmendezs/mcp-fattura-elettronica-it) |
| 🇵🇱 Pologne | [mcp-ksef-pl](https://github.com/cmendezs/mcp-ksef-pl) |
| 🇪🇸 Espagne | [mcp-facturacion-electronica-es](https://github.com/cmendezs/mcp-facturacion-electronica-es) |

## Licence

Apache 2.0, voir [LICENSE](LICENSE).
