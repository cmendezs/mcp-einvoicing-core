# mcp-einvoicing-core

[English](README.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Topics:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Pacchetto base per server MCP di fatturazione elettronica.

Fornisce classi base astratte, modelli Pydantic condivisi, utilità XML e un client HTTP
affinché i pacchetti specifici per paese (`mcp-facture-electronique-fr`, `mcp-fattura-elettronica-it`, `mcp-nfe-br`, ...)
condividano una base comune senza duplicare il codice.

---

## Contenuto del pacchetto

| Modulo | Contenuti | Utilizzato da |
|--------|----------|---------|
| `models.py` | `InvoiceParty`, `InvoiceLineItem`, `VATSummary`, `PaymentTerms`, `InvoiceDocument`, `DocumentValidationResult` | IT (generazione fatture strutturate), futuro BE/PL/DE/ES |
| `base_server.py` | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `EInvoicingMCPServer` | Tutti gli adattatori per paese |
| `xml_utils.py` | `format_amount`, `format_quantity`, `validate_date_iso`, `validate_iban`, `xml_element`, `xml_optional`, `format_error`, `filter_empty_values` | IT (estratto integralmente), futuri formati basati su XML |
| `http_client.py` | `TokenCache`, `OAuthConfig`, `BaseEInvoicingClient` (OAuth2 + senza autenticazione) | FR (estratto integralmente), futuri paesi basati su API |
| `exceptions.py` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` | Tutti gli adattatori per paese |
| `logging_utils.py` | `setup_logging`, `get_logger` | Tutti gli adattatori per paese |

## Installazione

```bash
pip install mcp-einvoicing-core
```

Questo pacchetto **non ha dipendenze specifiche per paese**. `lxml` (necessario per la validazione XSD
in IT e futuri paesi) viene dichiarato individualmente da ciascun pacchetto per paese.

## Architettura

```
mcp-einvoicing-core           ← questo pacchetto
  ├── BaseDocumentGenerator   ← astratto: generate(InvoiceDocument) → str
  ├── BaseDocumentValidator   ← astratto: validate(xml) → DocumentValidationResult
  ├── BaseDocumentParser      ← astratto: parse(xml) → dict
  ├── BaseLifecycleManager    ← astratto: submit/search/get_status (HTTP asincrono)
  ├── BasePartyValidator      ← astratto: validate_seller/buyer/tax_id
  ├── BaseEInvoicingClient    ← concreto: HTTP asincrono + OAuth2/senza auth/token
  ├── InvoiceDocument (Pydantic)  ← modello dati condiviso
  └── EInvoicingMCPServer     ← registro plugin che avvolge FastMCP

mcp-facture-electronique-fr   ← adattatore per paese (FR)
  ├── PAConfig(OAuthConfig)
  ├── FlowClient(BaseEInvoicingClient)      ← OAuth2, XP Z12-013 Allegato A
  ├── DirectoryClient(BaseEInvoicingClient) ← OAuth2, XP Z12-013 Allegato B
  └── FrLifecycleManager(BaseLifecycleManager)

mcp-fattura-elettronica-it    ← adattatore per paese (IT)
  ├── ItalyPartyValidator(BasePartyValidator)   ← Partita IVA modulo-10
  ├── FatturaGenerator(BaseDocumentGenerator)   ← FatturaPA XML v1.6.1
  ├── FatturaValidator(BaseDocumentValidator)   ← lxml XSD v1.6.1
  └── FatturaParser(BaseDocumentParser)         ← lxml xpath
```

## Modello di registrazione dei plugin

I pacchetti per paese registrano i propri strumenti su un'istanza FastMCP condivisa o autonoma:

```python
# Autonomo (server.py esistente, nessuna modifica necessaria)
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="…")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# Multi-paese (EInvoicingMCPServer opzionale)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="…")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

## Compatibilità con Claude Desktop / Cursor / Kiro

Le configurazioni esistenti per `mcp-facture-electronique-fr` e `mcp-fattura-elettronica-it`
**non richiedono modifiche**: nomi degli strumenti, firme, variabili di ambiente e punti di ingresso
(`server:main`) sono completamente preservati.

## Compatibilità con la roadmap

Il backlog aperto e la pianificazione degli sprint per paese sono in [`context-library/roadmap-2026.md`](../context-library/roadmap-2026.md). La tabella sottostante riflette la separazione canonica tra alberi di fattura EN 16931 e non-EN 16931 (vedi `CLAUDE.md`).

| Paese | Versione | Standard | Albero di fattura | Trasporto |
|-------|----------|----------|-------------------|-----------|
| [🇧🇪 BE](https://github.com/cmendezs/mcp-einvoicing-be) | v0.2.0 pubblicato | Peppol BIS 3.0 / PINT-BE | `BEInvoice(EN16931Invoice)` | Rete Peppol (AS4) |
| [🇫🇷 FR](https://github.com/cmendezs/mcp-facture-electronique-fr) | v0.4.0 pubblicato | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | `EN16931Invoice` (obiettivo — vedi FR-SC-1) | Ibrido / PPF + PDP |
| [🇩🇪 DE](https://github.com/cmendezs/mcp-einvoicing-de) | v0.3.1 pubblicato | ZUGFeRD 2.x / XRechnung 3.x | `ZUGFeRDInvoice(EN16931Invoice)` | Diretto + lookup partecipante Peppol |
| [🇮🇹 IT](https://github.com/cmendezs/mcp-fattura-elettronica-it) | v0.2.5 pubblicato | FatturaPA v1.2.x | EN 16931 (CIUS italiano) | Diretto / SdI |
| [🇵🇱 PL](https://github.com/cmendezs/mcp-ksef-pl) | v0.2.2 pubblicato | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | `KSeFInvoice(EN16931Invoice)` | API diretta + Peppol |
| [🇪🇸 ES](https://github.com/cmendezs/mcp-facturacion-electronica-es) | v0.2.0 pubblicato | Factura-e / VeriFactu / SII / FACe | Doppio: `EN16931Invoice` (Factura-e) + `InvoiceDocument` (VeriFactu, SII) | API diretta (mTLS / OAuth2) |
| [🇧🇷 BR](https://github.com/cmendezs/mcp-nfe-br) | v0.5.2 pubblicato | NF-e / NFC-e (modelo 55/65, schema 4.00); NFS-e Nacional v1.01 | `BRInvoice(InvoiceDocument)` + `NFSeDocument(InvoiceDocument)` | mTLS diretto / SEFAZ + Gov.br OAuth2 / ADN |

Paesi sul radar di pianificazione (non ancora scaffoldati — vedi la sezione "New country packages" in [`roadmap-2026.md`](../context-library/roadmap-2026.md)): IN, MX, RO, CO, CL, PE, VN, EG, HU, GR, KR, ID, EC, UY (categoria 1 — clearance pienamente attiva); SG, MY, SA, NG, IL, PY, PH (categoria 2 — rollout nel 2026); UAE, OM, SK, PT, DK, ZA (categoria 3 — transizione o fine 2026/2027). Le giurisdizioni UE/APAC/NA volontarie sono di categoria 4.

## Note architetturali

### Interfaccia di trasporto

Con la crescita del numero di adattatori, un'astrazione `TransportInterface` nel core preverrà la duplicazione tra paesi che condividono lo stesso livello di trasporto. Copertura attuale degli adattatori:

| Trasporto | Paesi |
|-----------|-------|
| **API diretta** (clearance / reporting / B2G) | FR (Chorus Pro + PDP/PPF), ES (AEAT + FACe), PL (KSeF), IT (SdI pianificato) |
| **mTLS verso webservice governativo** | BR (SEFAZ), ES (VeriFactu, SII) |
| **Rete Peppol (AS4)** | BE, DE (pianificato tramite DE-PEPPOL-1, v0.5.0) |
| **OAuth2 verso hub governativo** | BR (Gov.br ADN per NFS-e Nacional) |

Una `TransportInterface` dedicata è tracciata come lavoro architetturale; oggi ogni adattatore paese estende direttamente `BaseEInvoicingClient` con la modalità di autenticazione di cui ha bisogno (`AuthMode.OAUTH2_CLIENT_CREDENTIALS`, `AuthMode.MTLS`, `AuthMode.BEARER_TOKEN`, `AuthMode.NONE`).

### Formati wire EN 16931

Il pacchetto core fornisce `EN16931UBLSerializer`/`EN16931UBLParser` e `EN16931CIISerializer`/`EN16931CIIParser` (dalla v1.3.0) in modo che gli adattatori paese UE non reimplementino la serializzazione UBL 2.1 o CII D16B. I nuovi pacchetti paese UE dovrebbero estendere queste classi anziché scrivere uno stack XML parallelo.

### ViDA / DRR (2030)

Entro luglio 2030, tutti i sistemi nazionali dovranno allinearsi ai Digital Reporting Requirements (DRR) dell'UE per le transazioni transfrontaliere. L'utilizzo di **EN 16931** come radice canonica della fattura UE (`EN16931Invoice`) rende già il lato envelope della fattura pronto per il futuro: gli adattatori paese traducono `EN16931Invoice` nel formato wire locale, non il contrario. Il ciclo di vita della trasmissione DRR (trasmissione in tempo reale di dati di transazione strutturati a un registro centrale UE, emissione di ID di transazione, riconciliazione 4-corner transfrontaliera) non è modellato nel core oggi ed è tracciato come workstream separato in [`roadmap-2026.md`](../context-library/roadmap-2026.md); non confondere "supporta EN 16931 / Peppol" con "supporta ViDA DRR".

## Altri server MCP per la fatturazione elettronica

| Paese | Server |
|-------|--------|
| 🌐 Globale | [`mcp-einvoicing-core`](https://github.com/cmendezs/mcp-einvoicing-core) |
| 🇧🇪 Belgio | [`mcp-einvoicing-be`](https://github.com/cmendezs/mcp-einvoicing-be) |
| 🇧🇷 Brasile | [`mcp-nfe-br`](https://github.com/cmendezs/mcp-nfe-br) |
| 🇫🇷 Francia | [`mcp-facture-electronique-fr`](https://github.com/cmendezs/mcp-facture-electronique-fr) |
| 🇩🇪 Germania | [`mcp-einvoicing-de`](https://github.com/cmendezs/mcp-einvoicing-de) |
| 🇮🇹 Italia | [`mcp-fattura-elettronica-it`](https://github.com/cmendezs/mcp-fattura-elettronica-it) |
| 🇵🇱 Polonia | [`mcp-ksef-pl`](https://github.com/cmendezs/mcp-ksef-pl) |
| 🇪🇸 Spagna | [`mcp-facturacion-electronica-es`](https://github.com/cmendezs/mcp-facturacion-electronica-es) |

## Licenza

Apache 2.0, consultare [LICENSE](LICENSE).
