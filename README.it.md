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

| Paese | Stato | Standard | Trasporto | Eredita | Sovrascrive | Lacune note |
|---------|--------|----------|-----------|----------|-----------|------------|
| [🇧🇪 BE](https://github.com/cmendezs/mcp-einvoicing-be) | ✅ Completato | Peppol BIS 3.0 | AS4 / Peppol | tutte le classi base | `generate()` → UBL 2.1, `validate()` → Schematron EN16931 | Nessuna |
| [🇫🇷 FR](https://github.com/cmendezs/mcp-facture-electronique-fr) | ✅ Completato | XP Z12-013 | Ibrido / hub PPF | `BaseEInvoicingClient`, `BaseLifecycleManager` | `submit_lifecycle_status`, `healthcheck` | Nessuna |
| [🇩🇪 DE](https://github.com/cmendezs/mcp-einvoicing-de) | ✅ Completato | ZUGFeRD / XRechnung | AS4 / Peppol | tutte le classi base | `generate()` restituisce byte PDF (base64) | Ambiguità tipo di ritorno `generate()`: `str` vs `bytes` |
| [🇮🇹 IT](https://github.com/cmendezs/mcp-fattura-elettronica-it) | ✅ Completato | FatturaPA v1.6.1 | Diretto / SDI | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BasePartyValidator` | tutti i metodi astratti | `to_invoice_document()` non ancora implementato |
| [🇵🇱 PL](https://github.com/cmendezs/mcp-ksef-pl) | ✅ Completato | KSeF FA(2) | API diretta | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseLifecycleManager` | flusso autenticazione sessione KSeF | Modalità `MTLS` non ancora implementata |
| [🇪🇸 ES](https://github.com/cmendezs/mcp-facturacion-electronica-es) | ✅ Completato | FACeB2B / FacturaE | API diretta | tutte le classi base | autenticazione mTLS | Modalità `MTLS` non ancora implementata |
| [🇧🇷 BR](https://github.com/cmendezs/mcp-nfe-br) | 🚧 In corso | NF-e / NFC-e (schema 4.00) | API diretta / SEFAZ | `BasePartyValidator` | validazione CPF/CNPJ | Generazione NF-e/NFC-e e integrazione SEFAZ pianificate |
| 🇷🇴 RO | 📋 Backlog | RO-UBL (EN 16931) | API diretta / clearance | `BaseDocumentGenerator`, `BaseLifecycleManager` | flusso clearance ANAF | Variante `BaseSchematronValidator` necessaria |
| 🇬🇷 GR | 📋 Backlog | myDATA XML | API diretta / reporting | `BaseEInvoicingClient`, `BaseLifecycleManager` | flusso autenticazione + reporting myDATA | Client API myDATA non ancora progettato |
| 🇳🇱🇸🇪🇩🇰🇳🇴 Nordici/NL | 📋 Backlog | Peppol BIS 3.0 / UBL | AS4 / Peppol | tutte le classi base | `generate()` → UBL 2.1, `validate()` → Schematron | Riutilizza il livello di trasporto AS4 di BE |
| 🇵🇹 PT | 📋 Backlog | CIUS-PT + QR Code | Firma / diretto | `BaseDocumentGenerator`, `BaseDocumentValidator` | firma qualificata + iniezione QR | Integrazione firma qualificata non progettata |

## Note architetturali

### Interfaccia di trasporto

Con la crescita del numero di adattatori, un'astrazione `TransportInterface` nel core preverrà la duplicazione tra paesi che condividono lo stesso livello di trasporto:

| Trasporto | Paesi |
|-----------|-----------|
| **API diretta** (clearance / reporting) | FR, RO, GR, HU |
| **AS4 / rete Peppol** | BE, DE, Nordici/NL |
| **Ibrido / hub** | FR (doppio percorso PPF/PDP) |

### Germania: 80% di riutilizzo da FR

Il mandato tedesco (attivo da gennaio 2025 per la ricezione B2B) favorisce fortemente ZUGFeRD/Factur-X, lo stesso modello XML incorporato in PDF del profilo francese Factur-X. La logica di generazione e validazione XML di `mcp-facture-electronique-fr` può essere riutilizzata con modifiche minime, rendendo DE l'adattatore successivo a minor costo dopo BE.

### ViDA / DRR (2030)

Entro luglio 2030, tutti i sistemi nazionali dovranno allinearsi al Digital Reporting Requirement dell'UE per le transazioni transfrontaliere. L'utilizzo di **EN 16931** come modello dati interno `InvoiceDocument` in questo pacchetto core rende già il progetto pronto per il futuro: gli adattatori per paese traducono da EN 16931 al formato locale, non il contrario.

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
