# mcp-einvoicing-core

[English](README.md) | [Francais](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Espanol](README.es.md) | [Portugues (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Topics:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Paquet de base pour les serveurs MCP de facturation electronique.

Fournit des modeles Pydantic partages, un arbre de facture EN 16931, des serialiseurs UBL/CII,
un client HTTP OAuth2, une recherche SMP Peppol, des primitives de signature numerique et un
framework d'audit de conformite afin que les paquets par pays partagent un socle commun sans
dupliquer le code.

---

## Ce que ce paquet fournit

| Module | Contenu |
|--------|---------|
| `models` | `InvoiceDocument`, `InvoiceParty`, `InvoiceLineItem`, `PartyAddress`, `VATSummary`, `PaymentTerms`, `DocumentValidationResult`, `TaxIdentifier` (validateurs de numeros fiscaux par pays : IT, FR, DE, BE, ES, PL, BR), `TaxIdValidationResult` |
| `en16931` | `EN16931Invoice`, `EN16931Party`, `EN16931LineItem`, `EN16931Address`, `EN16931Tax`, `EN16931AllowanceCharge`, `EN16931PaymentMeans` |
| `credit_note` | `EN16931CreditNote` (codes type 381/383/384/385), `BillingReference` |
| `wire_formats` | `EN16931UBLSerializer`, `EN16931UBLParser`, `EN16931CIISerializer`, `EN16931CIIParser`, `UBL_NSMAP`, `CII_NSMAP` |
| `convert` | `Syntax` (UBL, CII), `convert_wire_format` (detection automatique de la source, serialisation vers la cible) |
| `base_server` | `EInvoicingMCPServer`, `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `SubmitResult`, `assert_not_read_only`, `scrub` |
| `http_client` | `BaseEInvoicingClient` (OAuth2, mTLS, bearer, cle API, aucun), `OAuthConfig`, `OAuthValues`, `TokenCache`, `AuthMode` |
| `peppol` | `PeppolSMPClient`, `PeppolParticipantId`, `PeppolServiceInfo`, `PeppolLookupResult`, `PeppolEnvironment`, `PEPPOL_BIS_BILLING_30`, `resolve_naptr` (diagnostic DNS U-NAPTR/SML autonome) |
| `peppol.tools` | `register_peppol_tools` (plugin FastMCP montable : recherche de participant, point de terminaison de service, diagnostic DNS, envoi AS4, plus 8 outils de listes de codes eDEC), `default_id_adapter`, `IdentifierAdapter` (contrat d'adaptateur d'identifiant national) |
| `peppol.codelists` | `CodeList`, `CodelistNotConfiguredError`, `load_codelist` et les fonctions de recherche eDEC (types de documents, processus, schemas d'identifiants participants, profils de transport, cas d'usage SPIS). Necessite `EINVOICING_PEPPOL_CODELIST_DIR`, voir Configuration ci-dessous |
| `peppol.transport` | `AS4MessageEnvelope`, `AS4TransportClient`, `AS4ReceiptHandler`, `PeppolTransmitter`, `AS4Receipt`, `AS4Credentials` (transmission sortante Peppol AS4) |
| `schematron` | `SchematronValidator` (XSLT 1.0), `SaxonSchematronValidator` (XSLT 2.0/3.0, extra optionnel `[xslt2]`), `load_schematron_validator` (factory de selection automatique), `get_xslt_version`, `BaseStructuredValidator`, `BaseXSDValidator`, `BaseJSONValidator`, `ValidationMessage`, `ValidationResult` |
| `schematron_artifacts` | `en16931_base_schematron_validator` (Schematron de base CEN EN16931 compile et fourni — regles `BR-*` uniquement, sans le surensemble Peppol ; extra optionnel `[xslt2]`) |
| `digital_signature` | `BaseDocumentSigner`, `XAdESEPESSigner`, `XAdESSignerConfig`, `XMLDSigSigner`, `XMLDSigSignerConfig` |
| `endpoints` | `BaseEnvironmentEndpoints`, `EndpointSet`, `EndpointEnvironment` (routage d'URL sandbox/production) |
| `routing` | `RoutingIdentifier` (validateurs statiques : `validate_de_leitweg`), `RoutingIdValidationResult` |
| `profile_registry` | `ProfileEntry`, `ProfileRegistry`, `profile_registry`, `set_profile_registry` |
| `pdf` | `PDFEmbedder` (integration XML dans PDF/A-3) ; `extract(filename=None)` essaie successivement les noms de fichiers canoniques Factur-X/XRechnung/ZUGFeRD, `identify()` lit les metadonnees XMP pour detecter un PDF hybride et son niveau de conformite |
| `pdf_tools` | `register_pdf_tools` (plugin FastMCP montable : `identify_and_extract_pdf`), `identify_and_extract_pdf` |
| `qr` | `generate_qr_png_base64` |
| `xml_utils` | `format_amount`, `format_quantity`, `xml_element`, `xml_optional`, `validate_date_iso`, `validate_iban`, `resolve_xml_input`, `mark_untrusted`, `mark_untrusted_fields`, `filter_empty_values`, `format_error` |
| `download_rules` | `DownloadSpec`, `download_artefacts` |
| `testing` | `InvoiceFixtureFactory` (fixtures pytest partagees) |
| `audit_log` | `AuditLog`, `AuditAction`, `get_audit_log` |
| `confirmation` | `ConfirmationGate`, `ConfirmationStore` (porte de validation humaine) |
| `exceptions` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `SchematronValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` |
| `logging_utils` | `setup_logging`, `get_logger` |
| `audit` | Framework d'audit de conformite : `AuditReport`, `CheckResult`, `CheckFinding`, constantes de severite, `make_report`, `render_summary_table`, `parse_audit_args`, `run_check_core_coverage`, `run_check_version_compatibility`, `run_check_known_shared_helpers`, `TaxRate`, `load_rates` (extra optionnel `[audit]`) |

## Paquets pays

| Pays | Paquet | Norme | Perimetre | Statut de couverture |
|------|--------|-------|-----------|-----------------------|
| France | [`mcp-facture-electronique-fr`](https://github.com/cmendezs/mcp-facture-electronique-fr) | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | B2B, deploiement progressif a partir du 1er septembre 2026 | En service |
| Allemagne | [`mcp-einvoicing-de`](https://github.com/cmendezs/mcp-einvoicing-de) | ZUGFeRD 2.x / XRechnung 3.x | B2B, progressif de 2025 a 2028 | En service |
| Belgique | [`mcp-einvoicing-be`](https://github.com/cmendezs/mcp-einvoicing-be) | Peppol BIS 3.0 / PINT-BE | B2B, 1er janvier 2026 | En service ; regles de surcouche specifiques Peppol non verifiees (EN 16931 de base uniquement) |
| Italie | [`mcp-fattura-elettronica-it`](https://github.com/cmendezs/mcp-fattura-elettronica-it) | FatturaPA / SDI | B2G + B2B + B2C, obligatoire depuis 2019 (B2G depuis 2014) | En service |
| Pologne | [`mcp-ksef-pl`](https://github.com/cmendezs/mcp-ksef-pl) | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | B2B, progressif de fevrier 2026 a janvier 2027 | En service ; flux de session par lots non implemente |
| Espagne | [`mcp-facturacion-electronica-es`](https://github.com/cmendezs/mcp-facturacion-electronica-es) | Factura-e / VeriFactu / SII / FACe | En attente de l'Orden Ministerial, visee pour le 2026-10-01 | En service pour VeriFactu/SII ; integration du format B2B bloquee dans l'attente de l'Orden Ministerial |
| Bresil | [`mcp-nfe-br`](https://github.com/cmendezs/mcp-nfe-br) | NF-e / NFC-e (modelo 55/65, schema 4.00) / NFS-e Nacional | B2B (NF-e) + B2C (NFC-e), obligatoires depuis 2008 | En service ; reforme fiscale IBS/CBS en cours de deploiement jusqu'en 2033 |

## Installation

```bash
pip install mcp-einvoicing-core
```

Pour le framework d'audit de conformite (utilise par la CI des paquets pays) :

```bash
pip install mcp-einvoicing-core[audit]
```

Pour la validation Schematron XSLT 2.0/3.0 (`SaxonSchematronValidator` — necessaire pour les jeux de regles Schematron utilisant des constructions XPath 2.0+, ex. FNFE-MPE Factur-X 1.08 / ZUGFeRD) :

```bash
pip install mcp-einvoicing-core[xslt2]
```

## Configuration

| Variable | Utilisee par | Objet |
|---|---|---|
| `EINVOICING_PEPPOL_CODELIST_DIR` | `peppol.codelists` (et les outils de listes de codes de `peppol.tools`) | Repertoire local contenant votre propre copie des listes de codes OpenPeppol eDEC. **Non fourni avec ce paquet** : les listes de codes eDEC ne disposent d'aucun droit de redistribution confirme de la part d'OpenPeppol, donc le core ne fournit que l'analyseur et les outils de recherche, jamais les donnees elles-memes. Telechargez l'export "as GeneriCode" pour chaque artefact (Document Types, Participant Identifier Schemes, Processes, Transport Profiles, SPIS Use Case) depuis [docs.peppol.eu/edelivery/codelists](https://docs.peppol.eu/edelivery/codelists/index.html) et faites pointer cette variable vers le repertoire les contenant. Les noms de fichiers sont reconnus par prefixe, donc une montee de version (ex. v9.7 vers v9.8) ne necessite aucune modification de code. Sans cette variable, les outils de listes de codes renvoient un resultat `configured: false` avec des instructions de configuration plutot que de lever une exception. |
| `EINVOICING_SMP_ALLOWLIST` | `peppol` (`PeppolSMPClient`, `resolve_naptr`) | Suffixes de noms d'hote separes par des virgules pour etendre la liste blanche integree des points d'acces Peppol utilisee lors de la validation d'un nom d'hote SMP resolu. |

## Architecture

Les paquets pays heritent des abstractions du core et enregistrent leurs outils sur un serveur MCP partage ou autonome :

```
mcp-einvoicing-core
  ├── EN16931Invoice / InvoiceDocument  ← modeles de facture canoniques
  ├── EN16931CreditNote                 ← avoir (codes type 381/383/384/385)
  ├── EN16931UBL/CII Serializer/Parser  ← aller-retour format filaire
  ├── convert_wire_format               ← conversion CII ↔ UBL
  ├── BaseDocumentGenerator/Validator/Parser/LifecycleManager
  ├── BaseEInvoicingClient              ← HTTP asynchrone (OAuth2/mTLS/bearer/cle API)
  ├── PeppolSMPClient                   ← recherche de participant via SMP/SML
  ├── PeppolTransmitter                 ← transmission sortante AS4
  ├── BaseDocumentSigner                ← XAdES-EPES / XMLDSig
  ├── BaseEnvironmentEndpoints          ← routage d'URL sandbox/production
  ├── RoutingIdentifier                 ← validation d'identifiants de routage par pays
  ├── EInvoicingMCPServer               ← registre de plugins encapsulant FastMCP
  └── Framework d'audit                 ← controles de conformite par paquet
```

## Patron d'enregistrement de plugins

Les paquets pays enregistrent leurs outils sur une instance FastMCP partagee ou autonome :

```python
# Autonome
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="...")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# Multi-pays (EInvoicingMCPServer optionnel)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="...")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

Le core fournit egalement son propre plugin d'outils Peppol montable afin que les paquets pays
cessent de reimplementer la recherche SMP et l'envoi AS4. Fournissez un adaptateur d'identifiant
national (une petite fonction qui normalise un numero national brut, par exemple un numero de
TVA, en un identifiant de participant Peppol `"<schema>:<valeur>"`) :

```python
from mcp_einvoicing_core.peppol.tools import register_peppol_tools

def be_id_adapter(identifier: str) -> str:
    if ":" in identifier:
        return identifier
    return f"0208:{normalize_vat_be(identifier)[2:]}"  # schema KBO/BCE

server.register_plugin(
    lambda m: register_peppol_tools(m, id_adapter=be_id_adapter), "peppol"
)
```

Cela enregistre `peppol_lookup_participant`, `peppol_get_service_endpoint`, `resolve_peppol_dns`,
`peppol_send`, ainsi que 8 outils de listes de codes OpenPeppol eDEC (voir Configuration
ci-dessus pour `EINVOICING_PEPPOL_CODELIST_DIR`, necessaire pour les outils de listes de codes).

## Compatibilite Claude Desktop / Cursor / Kiro

Les configurations existantes pour les paquets pays ne necessitent **aucune modification** :
les noms d'outils, les signatures, les variables d'environnement et les points d'entree
(`server:main`) sont entierement preserves.

## Licence

Apache 2.0, voir [LICENSE](LICENSE).
