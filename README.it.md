# mcp-einvoicing-core

[English](README.md) | [Francais](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Espanol](README.es.md) | [Portugues (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Topics:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Pacchetto base per server MCP di fatturazione elettronica.

Fornisce modelli Pydantic condivisi, un albero di fattura EN 16931, serializzatori UBL/CII,
un client HTTP OAuth2, lookup SMP Peppol, primitive di firma digitale e un framework di
audit di conformita, affinche i pacchetti per paese condividano una base comune senza
duplicare il codice.

---

## Contenuto del pacchetto

| Modulo | Contenuti |
|--------|----------|
| `models` | `InvoiceDocument`, `InvoiceParty`, `InvoiceLineItem`, `PartyAddress`, `VATSummary`, `PaymentTerms`, `DocumentValidationResult`, `TaxIdentifier` (validatori di codici fiscali per paese: IT, FR, DE, BE, ES, PL, BR, AE, SG), `TaxIdValidationResult` |
| `en16931` | `EN16931Invoice`, `EN16931Party`, `EN16931LineItem`, `EN16931Address`, `EN16931Tax`, `EN16931AllowanceCharge`, `EN16931PaymentMeans` |
| `credit_note` | `EN16931CreditNote` (codici tipo 381/383/384/385), `BillingReference` |
| `ubl_documents` | `BaseUBLDocument` — involucro condiviso per famiglie di documenti UBL/Peppol non fattura (Peppol Ordering, estensioni giurisdizionali); esplicitamente al di fuori dell'albero `InvoiceDocument`/`EN16931Invoice` |
| `wire_formats` | `EN16931UBLSerializer`, `EN16931UBLParser`, `EN16931CIISerializer`, `EN16931CIIParser`, `UBL_NSMAP`, `CII_NSMAP` |
| `convert` | `Syntax` (UBL, CII), `convert_wire_format` (rilevamento automatico della sorgente, serializzazione verso il target) |
| `base_server` | `EInvoicingMCPServer`, `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `SubmitResult`, `assert_not_read_only`, `scrub` |
| `http_client` | `BaseEInvoicingClient` (OAuth2, mTLS, bearer, API key, nessuno), `OAuthConfig`, `OAuthValues`, `TokenCache`, `AuthMode` |
| `peppol` | `PeppolSMPClient`, `PeppolParticipantId`, `PeppolServiceInfo`, `PeppolLookupResult`, `PeppolEnvironment`, `PEPPOL_BIS_BILLING_30`, `resolve_naptr` (diagnostica DNS U-NAPTR/SML autonoma) |
| `peppol.tools` | `register_peppol_tools` (plugin FastMCP montabile: lookup partecipante, endpoint di servizio, diagnostica DNS, invio AS4, ricerca su Directory, oltre a 8 strumenti per le liste codici eDEC), `default_id_adapter`, `IdentifierAdapter` (contratto dell'adattatore di identificativo nazionale) |
| `peppol.codelists` | `CodeList`, `CodelistNotConfiguredError`, `load_codelist` e le funzioni di ricerca eDEC (tipi di documento, processi, schemi di identificativo partecipante, profili di trasporto, casi d'uso SPIS). Richiede `EINVOICING_PEPPOL_CODELIST_DIR`, vedere Configurazione piu sotto |
| `genericode` | `parse_genericode`, `CodeList`, `CodelistNotConfiguredError` — parser condiviso per il formato OASIS Genericode 1.0 (usato da `peppol.codelists` e `en16931_codelists`) |
| `en16931_codelists` | `en16931_codelist_tools.register_en16931_codelist_tools` (plugin FastMCP montabile: ricerca per paese, valuta, ICD, UNCL1001/1153/4461/5305, motivo di abbuono/articolo/addebito, MIME, EAS, VATEX). Richiede `EINVOICING_EN16931_CODELIST_DIR`, vedere Configurazione piu sotto |
| `peppol.directory` | `PeppolDirectoryClient` (ricerca REST pubblica su Peppol Directory, senza autenticazione), `PeppolDirectorySearchResult`, `PeppolBusinessCard`, `PeppolBusinessEntity` |
| `peppol.transport` | `AS4MessageEnvelope`, `AS4TransportClient`, `AS4ReceiptHandler`, `PeppolTransmitter`, `AS4Receipt`, `AS4Credentials` (trasmissione Peppol AS4 in uscita, ora con firma reale dei messaggi WS-Security); `AS4InboundHandler`, `AS4InboundMessage`, `AS4InboundError`, `StandardBusinessDocumentHeader` (ricevitore AS4 in ingresso, ruolo C3); `sign_as4_message`, `verify_as4_signature` (primitive WS-Security) |
| `peppol.trust` | `PeppolTrustStore`, `validate_certificate_chain`, `check_revocation`, `verify_smp_signature` — convalida della catena PKI, della revoca e delle firme OpenPeppol. Richiede `EINVOICING_PEPPOL_PKI_DIR` (certificati radice non ancora pubblicati da OpenPeppol alla data di questa versione — logica soltanto, in attesa che vengano forniti) |
| `peppol.reporting` | `parse_eusr`, `parse_tsr`, `validate_eusr`, `validate_tsr` — modelli e convalida dei report statistici EUSR/TSR dei fornitori di servizi Peppol (XSD e Schematron inclusi, extra opzionale `[xslt2]`) |
| `peppol.mls` | `parse_mls`, `validate_mls`, `build_mls` — modello e convalida del Peppol Message Level Status (MLS) (Schematron incluso, extra opzionale `[xslt2]`) |
| `schematron` | `SchematronValidator` (XSLT 1.0), `SaxonSchematronValidator` (XSLT 2.0/3.0, extra opzionale `[xslt2]`), `load_schematron_validator` (factory a selezione automatica), `get_xslt_version`, `BaseStructuredValidator`, `BaseXSDValidator`, `XSDValidator` (validatore XSD concreto generico), `BaseJSONValidator`, `ValidationMessage`, `ValidationResult` |
| `schematron_artifacts` | `en16931_base_schematron_validator` (Schematron di base CEN EN16931 compilato e incluso — solo regole `BR-*`, senza overlay Peppol; extra opzionale `[xslt2]`) |
| `digital_signature` | `BaseDocumentSigner`, `XAdESEPESSigner`, `XAdESSignerConfig`, `XMLDSigSigner`, `XMLDSigSignerConfig` |
| `endpoints` | `BaseEnvironmentEndpoints`, `EndpointSet`, `EndpointEnvironment` (routing URL sandbox/produzione) |
| `routing` | `RoutingIdentifier` (validatori statici: `validate_de_leitweg`), `RoutingIdValidationResult` |
| `profile_registry` | `ProfileEntry`, `ProfileRegistry`, `profile_registry`, `set_profile_registry` |
| `pdf` | `PDFEmbedder` (incorporamento XML in PDF/A-3); `extract(filename=None)` prova in sequenza i nomi file canonici Factur-X/XRechnung/ZUGFeRD, `identify()` legge i metadati XMP per rilevare un PDF ibrido e il suo livello di conformita |
| `pdf_tools` | `register_pdf_tools` (plugin FastMCP montabile: `identify_and_extract_pdf`), `identify_and_extract_pdf` |
| `qr` | `generate_qr_png_base64` |
| `xml_utils` | `format_amount`, `format_quantity`, `xml_element`, `xml_optional`, `validate_date_iso`, `validate_iban`, `resolve_xml_input`, `mark_untrusted`, `mark_untrusted_fields`, `filter_empty_values`, `format_error` |
| `download_rules` | `DownloadSpec`, `download_artefacts` |
| `testing` | `InvoiceFixtureFactory` (fixture pytest condivise) |
| `audit_log` | `AuditLog`, `AuditAction`, `get_audit_log` |
| `confirmation` | `ConfirmationGate`, `ConfirmationStore` (gate di validazione umana) |
| `exceptions` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `SchematronValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` |
| `logging_utils` | `setup_logging`, `get_logger` |
| `audit` | Framework di audit di conformita: `AuditReport`, `CheckResult`, `CheckFinding`, costanti di severita, `make_report`, `render_summary_table`, `parse_audit_args`, `run_check_core_coverage`, `run_check_version_compatibility`, `run_check_known_shared_helpers`, `TaxRate`, `load_rates` (extra opzionale `[audit]`) |

## Pacchetti per paese

| Paese | Pacchetto | Standard | Ambito | Stato di copertura |
|-------|-----------|----------|--------|---------------------|
| 🇧🇪 Belgio | [`mcp-einvoicing-be`](https://github.com/cmendezs/mcp-einvoicing-be) | Peppol BIS 3.0 / PINT-BE | B2B, 1 gennaio 2026 | Attivo; regole di overlay specifiche Peppol non verificate (solo EN 16931 di base) |
| 🇧🇷 Brasile | [`mcp-nfe-br`](https://github.com/cmendezs/mcp-nfe-br) | NF-e / NFC-e (modelo 55/65, schema 4.00) / NFS-e Nacional | B2B (NF-e) + B2C (NFC-e), entrambi obbligatori dal 2008 | Attivo; riforma fiscale IBS/CBS in corso fino al 2033 |
| 🇫🇷 Francia | [`mcp-facture-electronique-fr`](https://github.com/cmendezs/mcp-facture-electronique-fr) | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | B2B, adozione progressiva a partire dal 1 settembre 2026 | Attivo |
| 🇩🇪 Germania | [`mcp-einvoicing-de`](https://github.com/cmendezs/mcp-einvoicing-de) | ZUGFeRD 2.x / XRechnung 3.x | B2B, progressiva dal 2025 al 2028 | Attivo |
| 🇮🇹 Italia | [`mcp-fattura-elettronica-it`](https://github.com/cmendezs/mcp-fattura-elettronica-it) | FatturaPA / SDI | B2G + B2B + B2C, obbligatorio dal 2019 (B2G dal 2014) | Attivo |
| 🇵🇱 Polonia | [`mcp-ksef-pl`](https://github.com/cmendezs/mcp-ksef-pl) | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | B2B, progressiva da febbraio 2026 a gennaio 2027 | Attivo; flusso di sessione batch non implementato |
| 🇪🇸 Spagna | [`mcp-facturacion-electronica-es`](https://github.com/cmendezs/mcp-facturacion-electronica-es) | Factura-e / VeriFactu / SII / FACe | In attesa dell'Orden Ministerial, prevista per il 2026-10-01 | Attivo per VeriFactu/SII; integrazione del formato B2B bloccata in attesa dell'Orden Ministerial |

## Installazione

```bash
pip install mcp-einvoicing-core
```

Per il framework di audit di conformita (utilizzato dalla CI dei pacchetti per paese):

```bash
pip install mcp-einvoicing-core[audit]
```

Per la validazione Schematron XSLT 2.0/3.0 (`SaxonSchematronValidator` — necessario per i set di regole Schematron che usano costrutti XPath 2.0+, es. FNFE-MPE Factur-X 1.08 / ZUGFeRD):

```bash
pip install mcp-einvoicing-core[xslt2]
```

## Configurazione

| Variabile | Usata da | Scopo |
|---|---|---|
| `EINVOICING_PEPPOL_CODELIST_DIR` | `peppol.codelists` (e gli strumenti per le liste codici in `peppol.tools`) | Directory locale contenente una propria copia delle liste codici OpenPeppol eDEC. **Non incluse in questo pacchetto**: le liste codici eDEC non dispongono di alcuna concessione di ridistribuzione confermata da OpenPeppol, quindi il core fornisce solo il parser e gli strumenti di ricerca, mai i dati stessi. Scaricare l'export "as GeneriCode" per ciascun artefatto (Document Types, Participant Identifier Schemes, Processes, Transport Profiles, SPIS Use Case) da [docs.peppol.eu/edelivery/codelists](https://docs.peppol.eu/edelivery/codelists/index.html) e far puntare questa variabile alla directory che li contiene. I nomi dei file vengono riconosciuti tramite prefisso, quindi un aggiornamento di versione (es. da v9.7 a v9.8) non richiede modifiche al codice. Se non impostata, gli strumenti per le liste codici restituiscono un risultato `configured: false` con le istruzioni di configurazione, invece di generare un'eccezione. |
| `EINVOICING_EN16931_CODELIST_DIR` | `en16931_codelists` (e i relativi strumenti FastMCP) | Directory locale contenente una propria copia delle liste codici semantiche CEF EN 16931 (paese, valuta, ICD, UNCL1001/1153/4461/5305, motivo di abbuono/articolo/addebito, MIME, EAS, VATEX). **Non incluse in questo pacchetto**, stessa condizione delle liste eDEC sopra: scaricare il pacchetto di export "as GeneriCode" dalla pagina delle liste codici CEF EN 16931. I nomi dei file corrispondono esattamente (`Country.gc`, non un nome preceduto da un prefisso di versione). Se non impostata, gli strumenti restituiscono `configured: false`. |
| `EINVOICING_PEPPOL_PKI_DIR` | `peppol.trust` | Directory locale con le sottodirectory `test/` e `prod/` contenenti i certificati radice/intermedi della PKI OpenPeppol in formato PEM, usati per la convalida della catena di firma dei messaggi AS4 e delle risposte SMP. Non ancora pubblicati da OpenPeppol come dato incluso in alcun pacchetto: le funzioni di trust segnalano `trust_anchors_configured: false` finche questa variabile non viene impostata. |
| `EINVOICING_SMP_ALLOWLIST` | `peppol` (`PeppolSMPClient`, `resolve_naptr`) | Suffissi di hostname separati da virgola per estendere la lista consentita integrata dei punti di accesso Peppol, usata durante la convalida di un hostname SMP risolto. |

## Architettura

I pacchetti per paese ereditano dalle astrazioni del core e registrano i propri strumenti su un server MCP condiviso o autonomo:

```
mcp-einvoicing-core
  ├── EN16931Invoice / InvoiceDocument  ← modelli di fattura canonici
  ├── EN16931CreditNote                 ← nota di credito (codici tipo 381/383/384/385)
  ├── EN16931UBL/CII Serializer/Parser  ← round-trip formato wire
  ├── convert_wire_format               ← conversione CII ↔ UBL
  ├── BaseDocumentGenerator/Validator/Parser/LifecycleManager
  ├── BaseEInvoicingClient              ← HTTP asincrono (OAuth2/mTLS/bearer/API key)
  ├── PeppolSMPClient                   ← lookup partecipante via SMP/SML
  ├── PeppolTransmitter                 ← trasmissione AS4 in uscita
  ├── BaseDocumentSigner                ← XAdES-EPES / XMLDSig
  ├── BaseEnvironmentEndpoints          ← routing URL sandbox/produzione
  ├── RoutingIdentifier                 ← validazione ID di instradamento per paese
  ├── EInvoicingMCPServer               ← registro plugin che avvolge FastMCP
  └── Framework di audit                ← controlli di conformita per pacchetto
```

## Modello di registrazione dei plugin

I pacchetti per paese registrano i propri strumenti su un'istanza FastMCP condivisa o autonoma:

```python
# Autonomo
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="...")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# Multi-paese (EInvoicingMCPServer opzionale)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="...")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

Il core fornisce anche un proprio plugin di strumenti Peppol montabile, cosi che i pacchetti per
paese smettano di reimplementare il lookup SMP e l'invio AS4. Fornire un adattatore di
identificativo nazionale (una piccola funzione che normalizza un numero nazionale semplice, ad
esempio una partita IVA, in un identificativo partecipante Peppol `"<schema>:<valore>"`):

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

Questo registra `peppol_lookup_participant`, `peppol_get_service_endpoint`, `resolve_peppol_dns`,
`peppol_send`, `peppol_directory_search` e 8 strumenti per le liste codici OpenPeppol eDEC (vedere
Configurazione sopra per `EINVOICING_PEPPOL_CODELIST_DIR`, necessaria per gli strumenti delle liste
codici). Plugin montabili separati coprono le liste codici semantiche EN 16931
(`en16931_codelist_tools.register_en16931_codelist_tools`), il reporting Peppol
(`peppol.reporting_tools.register_peppol_reporting_tools`) e l'MLS
(`peppol.mls_tools.register_peppol_mls_tools`).

## Compatibilita con Claude Desktop / Cursor / Kiro

Le configurazioni esistenti per i pacchetti per paese **non richiedono modifiche**:
nomi degli strumenti, firme, variabili di ambiente e punti di ingresso (`server:main`)
sono completamente preservati.

## Licenza

Apache 2.0, consultare [LICENSE](LICENSE).
