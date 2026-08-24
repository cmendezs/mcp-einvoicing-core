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
| `peppol` | `PeppolSMPClient`, `PeppolParticipantId`, `PeppolServiceInfo`, `PeppolLookupResult`, `PeppolEnvironment`, `PEPPOL_BIS_BILLING_30`, `resolve_naptr` (eigenstaendige U-NAPTR/SML-DNS-Diagnose) |
| `peppol.tools` | `register_peppol_tools` (montierbares FastMCP-Plugin: Teilnehmer-Lookup, Service-Endpunkt, DNS-Diagnose, AS4-Versand, Directory-Suche, plus 8 eDEC-Codelisten-Tools), `default_id_adapter`, `IdentifierAdapter` (Vertrag fuer den nationalen Identifikator-Adapter) |
| `peppol.codelists` | `CodeList`, `CodelistNotConfiguredError`, `load_codelist` und die eDEC-Lookup-Funktionen (Dokumenttypen, Prozesse, Teilnehmer-ID-Schemata, Transportprofile, SPIS-Anwendungsfaelle). Erfordert `EINVOICING_PEPPOL_CODELIST_DIR`, siehe Konfiguration unten |
| `genericode` | `parse_genericode`, `CodeList`, `CodelistNotConfiguredError` — gemeinsamer OASIS-Genericode-1.0-Parser (verwendet von `peppol.codelists` und `en16931_codelists`) |
| `en16931_codelists` | `en16931_codelist_tools.register_en16931_codelist_tools` (montierbares FastMCP-Plugin: Lookup fuer Country, Currency, ICD, UNCL1001/1153/4461/5305, Allowance-/Item-/Charge-Reason, MIME, EAS, VATEX). Erfordert `EINVOICING_EN16931_CODELIST_DIR`, siehe Konfiguration unten |
| `peppol.directory` | `PeppolDirectoryClient` (oeffentliche Peppol-Directory-REST-Suche, ohne Authentifizierung), `PeppolDirectorySearchResult`, `PeppolBusinessCard`, `PeppolBusinessEntity` |
| `peppol.transport` | `AS4MessageEnvelope`, `AS4TransportClient`, `AS4ReceiptHandler`, `PeppolTransmitter`, `AS4Receipt`, `AS4Credentials` (ausgehende Peppol-AS4-Uebertragung, jetzt mit echter WS-Security-Nachrichtensignierung); `AS4InboundHandler`, `AS4InboundMessage`, `AS4InboundError`, `StandardBusinessDocumentHeader` (AS4-Eingangsempfaenger, C3-Rolle); `sign_as4_message`, `verify_as4_signature` (WS-Security-Primitiven) |
| `peppol.trust` | `PeppolTrustStore`, `validate_certificate_chain`, `check_revocation`, `verify_smp_signature` — Validierung der OpenPeppol-PKI-Zertifikatskette, -Sperrung und -Signatur. Erfordert `EINVOICING_PEPPOL_PKI_DIR` (Root-Zertifikate von OpenPeppol zum Zeitpunkt dieser Version noch nicht veroeffentlicht — bis dahin nur Logik, ohne Daten) |
| `peppol.reporting` | `parse_eusr`, `parse_tsr`, `validate_eusr`, `validate_tsr` — Modelle und Validierung fuer Peppol-EUSR/TSR-Statistikberichte der Diensteanbieter (gebuendeltes XSD + Schematron, optionales Extra `[xslt2]`) |
| `peppol.mls` | `parse_mls`, `validate_mls`, `build_mls` — Modell und Validierung fuer den Peppol Message Level Status (MLS) (gebuendeltes Schematron, optionales Extra `[xslt2]`) |
| `schematron` | `SchematronValidator` (XSLT 1.0), `SaxonSchematronValidator` (XSLT 2.0/3.0, optionales Extra `[xslt2]`), `load_schematron_validator` (automatische Backend-Auswahl), `get_xslt_version`, `BaseStructuredValidator`, `BaseXSDValidator`, `XSDValidator` (generischer konkreter XSD-Validator), `BaseJSONValidator`, `ValidationMessage`, `ValidationResult` |
| `schematron_artifacts` | `en16931_base_schematron_validator` (gebuendeltes, kompiliertes CEN-EN16931-Basis-Schematron — nur `BR-*`-Regeln, ohne Peppol-Overlay; optionales Extra `[xslt2]`) |
| `digital_signature` | `BaseDocumentSigner`, `XAdESEPESSigner`, `XAdESSignerConfig`, `XMLDSigSigner`, `XMLDSigSignerConfig` |
| `endpoints` | `BaseEnvironmentEndpoints`, `EndpointSet`, `EndpointEnvironment` (Sandbox-/Produktions-URL-Routing) |
| `routing` | `RoutingIdentifier` (statische Validatoren: `validate_de_leitweg`), `RoutingIdValidationResult` |
| `profile_registry` | `ProfileEntry`, `ProfileRegistry`, `profile_registry`, `set_profile_registry` |
| `pdf` | `PDFEmbedder` (XML-Einbettung in PDF/A-3); `extract(filename=None)` probiert nacheinander die kanonischen Factur-X/XRechnung/ZUGFeRD-Dateinamen, `identify()` liest XMP-Metadaten, um ein Hybrid-PDF und dessen Konformitaetsstufe zu erkennen |
| `pdf_tools` | `register_pdf_tools` (montierbares FastMCP-Plugin: `identify_and_extract_pdf`), `identify_and_extract_pdf` |
| `qr` | `generate_qr_png_base64` |
| `xml_utils` | `format_amount`, `format_quantity`, `xml_element`, `xml_optional`, `validate_date_iso`, `validate_iban`, `resolve_xml_input`, `mark_untrusted`, `mark_untrusted_fields`, `filter_empty_values`, `format_error` |
| `download_rules` | `DownloadSpec`, `download_artefacts` |
| `testing` | `InvoiceFixtureFactory` (gemeinsame pytest-Fixtures) |
| `audit_log` | `AuditLog`, `AuditAction`, `get_audit_log` |
| `confirmation` | `ConfirmationGate`, `ConfirmationStore` (Human-in-the-Loop-Gate) |
| `exceptions` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `SchematronValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` |
| `logging_utils` | `setup_logging`, `get_logger` |
| `audit` | Compliance-Audit-Framework: `AuditReport`, `CheckResult`, `CheckFinding`, Severity-Konstanten, `make_report`, `render_summary_table`, `parse_audit_args`, `run_check_core_coverage`, `run_check_version_compatibility`, `run_check_known_shared_helpers`, `TaxRate`, `load_rates` (optionales Extra `[audit]`) |

## Laenderpakete

| Land | Paket | Standard | Geltungsbereich | Abdeckungsstatus |
|------|-------|----------|------------------|-------------------|
| 🇧🇪 Belgien | [`mcp-einvoicing-be`](https://github.com/cmendezs/mcp-einvoicing-be) | Peppol BIS 3.0 / PINT-BE | B2B, 1. Januar 2026 | Aktiv; Peppol-spezifische Overlay-Regeln nicht geprueft (nur EN-16931-Basis) |
| 🇧🇷 Brasilien | [`mcp-nfe-br`](https://github.com/cmendezs/mcp-nfe-br) | NF-e / NFC-e (modelo 55/65, schema 4.00) / NFS-e Nacional | B2B (NF-e) + B2C (NFC-e), beide verpflichtend seit 2008 | Aktiv; IBS/CBS-Steuerreform laeuft bis 2033 |
| 🇫🇷 Frankreich | [`mcp-facture-electronique-fr`](https://github.com/cmendezs/mcp-facture-electronique-fr) | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | B2B, stufenweise Einfuehrung ab 1. September 2026 | Aktiv |
| 🇩🇪 Deutschland | [`mcp-einvoicing-de`](https://github.com/cmendezs/mcp-einvoicing-de) | ZUGFeRD 2.x / XRechnung 3.x | B2B, stufenweise 2025 bis 2028 | Aktiv |
| 🇮🇹 Italien | [`mcp-fattura-elettronica-it`](https://github.com/cmendezs/mcp-fattura-elettronica-it) | FatturaPA / SDI | B2G + B2B + B2C, verpflichtend seit 2019 (B2G seit 2014) | Aktiv |
| 🇵🇱 Polen | [`mcp-ksef-pl`](https://github.com/cmendezs/mcp-ksef-pl) | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | B2B, stufenweise Februar 2026 bis Januar 2027 | Aktiv; Batch-Session-Flow nicht implementiert |
| 🇪🇸 Spanien | [`mcp-facturacion-electronica-es`](https://github.com/cmendezs/mcp-facturacion-electronica-es) | Factura-e / VeriFactu / SII / FACe | Ausstehende Orden Ministerial, angestrebt fuer 2026-10-01 | Aktiv fuer VeriFactu/SII; B2B-Formatanbindung blockiert bis zur Orden Ministerial |

## Installation

```bash
pip install mcp-einvoicing-core
```

Fuer das Compliance-Audit-Framework (von der CI der Laenderpakete verwendet):

```bash
pip install mcp-einvoicing-core[audit]
```

Fuer die XSLT-2.0/3.0-Schematron-Validierung (`SaxonSchematronValidator` — erforderlich fuer Schematron-Regelwerke mit XPath-2.0+-Konstrukten, z. B. FNFE-MPE Factur-X 1.08 / ZUGFeRD):

```bash
pip install mcp-einvoicing-core[xslt2]
```

## Konfiguration

| Variable | Verwendet von | Zweck |
|---|---|---|
| `EINVOICING_PEPPOL_CODELIST_DIR` | `peppol.codelists` (und die Codelisten-Tools in `peppol.tools`) | Lokales Verzeichnis mit einer eigenen Kopie der OpenPeppol-eDEC-Codelisten. **Nicht in diesem Paket enthalten**: Fuer die eDEC-Codelisten liegt keine bestaetigte Weitergabeerlaubnis von OpenPeppol vor, daher liefert der Core nur den Parser und die Lookup-Tools, niemals die Daten selbst. Laden Sie den "as GeneriCode"-Export fuer jedes Artefakt (Document Types, Participant Identifier Schemes, Processes, Transport Profiles, SPIS Use Case) von [docs.peppol.eu/edelivery/codelists](https://docs.peppol.eu/edelivery/codelists/index.html) herunter und lassen Sie diese Variable auf das Verzeichnis mit diesen Dateien zeigen. Dateinamen werden anhand eines Praefixes erkannt, sodass ein Versionswechsel (z. B. v9.7 auf v9.8) keine Codeaenderung erfordert. Ist die Variable nicht gesetzt, liefern die Codelisten-Tools ein Ergebnis mit `configured: false` samt Einrichtungshinweisen, statt eine Ausnahme auszuloesen. |
| `EINVOICING_EN16931_CODELIST_DIR` | `en16931_codelists` (und dessen FastMCP-Tools) | Lokales Verzeichnis mit einer eigenen Kopie der semantischen EN-16931-Codelisten des CEF (Country, Currency, ICD, UNCL1001/1153/4461/5305, Allowance-/Item-/Charge-Reason, MIME, EAS, VATEX). **Nicht in diesem Paket enthalten**, gleiche Haltung wie bei den eDEC-Listen oben — laden Sie das "as GeneriCode"-Exportbuendel von der CEF-EN-16931-Codelisten-Seite herunter. Die Dateinamen muessen exakt uebereinstimmen (`Country.gc`, kein versionspraefigierter Name). Ist die Variable nicht gesetzt, liefern die Tools ein Ergebnis mit `configured: false`. |
| `EINVOICING_PEPPOL_PKI_DIR` | `peppol.trust` | Lokales Verzeichnis mit den Unterverzeichnissen `test/` und `prod/` fuer PEM-kodierte OpenPeppol-PKI-Root-/Zwischen-CA-Zertifikate, zur Validierung der Signaturkette fuer AS4-Nachrichtensignaturen und SMP-Antwortsignaturen. Von OpenPeppol bisher nirgendwo als gebuendelte Daten veroeffentlicht — die Trust-Funktionen melden `trust_anchors_configured: false`, solange diese Variable nicht gesetzt ist. |
| `EINVOICING_SMP_ALLOWLIST` | `peppol` (`PeppolSMPClient`, `resolve_naptr`) | Durch Kommas getrennte Hostname-Suffixe zur Erweiterung der eingebauten Peppol-Access-Point-Allowlist, die bei der Validierung eines aufgeloesten SMP-Hostnamens verwendet wird. |

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
  ├── PeppolTransmitter                 ← ausgehende AS4-Uebertragung
  ├── BaseDocumentSigner                ← XAdES-EPES / XMLDSig
  ├── BaseEnvironmentEndpoints          ← Sandbox-/Produktions-URL-Routing
  ├── RoutingIdentifier                 ← laenderspezifische Routing-ID-Validierung
  ├── EInvoicingMCPServer               ← Plugin-Registry ueber FastMCP
  └── Audit-Framework                   ← Compliance-Pruefungen pro Paket
```

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

Der Core stellt zudem ein eigenes montierbares Peppol-Tool-Plugin bereit, damit Laenderpakete
SMP-Lookup und AS4-Versand nicht mehr selbst implementieren muessen. Stellen Sie dafuer einen
nationalen Identifikator-Adapter bereit (eine kleine Funktion, die eine nationale Nummer, z. B.
eine USt-IdNr., in eine Peppol-Teilnehmer-ID `"<Schema>:<Wert>"` umwandelt):

```python
from mcp_einvoicing_core.peppol.tools import register_peppol_tools

def be_id_adapter(identifier: str) -> str:
    if ":" in identifier:
        return identifier
    return f"0208:{normalize_vat_be(identifier)[2:]}"  # KBO/BCE-Schema

server.register_plugin(
    lambda m: register_peppol_tools(m, id_adapter=be_id_adapter), "peppol"
)
```

Dadurch werden `peppol_lookup_participant`, `peppol_get_service_endpoint`, `resolve_peppol_dns`,
`peppol_send`, `peppol_directory_search` sowie 8 OpenPeppol-eDEC-Codelisten-Tools registriert
(siehe Konfiguration oben zu `EINVOICING_PEPPOL_CODELIST_DIR`, erforderlich fuer die
Codelisten-Tools). Eigene montierbare Plugins decken die semantischen EN-16931-Codelisten
(`en16931_codelist_tools.register_en16931_codelist_tools`), das Peppol-Reporting
(`peppol.reporting_tools.register_peppol_reporting_tools`) und MLS
(`peppol.mls_tools.register_peppol_mls_tools`) ab.

## Kompatibilitaet mit Claude Desktop / Cursor / Kiro

Bestehende Konfigurationen fuer Laenderpakete erfordern **keine Aenderungen**:
Tool-Namen, Signaturen, Umgebungsvariablen und Einstiegspunkte (`server:main`)
bleiben vollstaendig erhalten.

## Lizenz

Apache 2.0, siehe [LICENSE](LICENSE).
