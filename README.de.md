# mcp-einvoicing-core

[English](README.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Topics:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Basispaket für MCP-Server zur elektronischen Rechnungsstellung.

Stellt abstrakte Basisklassen, gemeinsame Pydantic-Modelle, XML-Hilfsfunktionen und einen HTTP-Client bereit,
damit länderspezifische Pakete (`mcp-facture-electronique-fr`, `mcp-fattura-elettronica-it`, `mcp-nfe-br`, ...)
auf einer gemeinsamen Grundlage aufbauen, ohne Code zu duplizieren.

---

## Was dieses Paket bereitstellt

| Modul | Inhalt | Verwendet von |
|-------|--------|---------------|
| `models.py` | `InvoiceParty`, `InvoiceLineItem`, `VATSummary`, `PaymentTerms`, `InvoiceDocument`, `DocumentValidationResult` | IT (strukturierte Rechnungsgenerierung), zukünftig BE/PL/DE/ES |
| `base_server.py` | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `EInvoicingMCPServer` | Alle Länderadapter |
| `xml_utils.py` | `format_amount`, `format_quantity`, `validate_date_iso`, `validate_iban`, `xml_element`, `xml_optional`, `format_error`, `filter_empty_values` | IT (wörtlich übernommen), zukünftige XML-basierte Formate |
| `http_client.py` | `TokenCache`, `OAuthConfig`, `BaseEInvoicingClient` (OAuth2 + ohne Authentifizierung) | FR (wörtlich übernommen), zukünftige API-basierte Länder |
| `exceptions.py` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` | Alle Länderadapter |
| `logging_utils.py` | `setup_logging`, `get_logger` | Alle Länderadapter |

## Installation

```bash
pip install mcp-einvoicing-core
```

Dieses Paket hat **keine länderspezifischen Abhängigkeiten**. `lxml` (für die XSD-Validierung
in IT und zukünftigen Ländern erforderlich) wird von jedem Länderpaket einzeln deklariert.

## Architektur

```
mcp-einvoicing-core           ← dieses Paket
  ├── BaseDocumentGenerator   ← abstrakt: generate(InvoiceDocument) → str
  ├── BaseDocumentValidator   ← abstrakt: validate(xml) → DocumentValidationResult
  ├── BaseDocumentParser      ← abstrakt: parse(xml) → dict
  ├── BaseLifecycleManager    ← abstrakt: submit/search/get_status (async HTTP)
  ├── BasePartyValidator      ← abstrakt: validate_seller/buyer/tax_id
  ├── BaseEInvoicingClient    ← konkret: async HTTP + OAuth2/ohne Auth/Token
  ├── InvoiceDocument (Pydantic)  ← gemeinsames Datenmodell
  └── EInvoicingMCPServer     ← Plugin-Registry mit FastMCP

mcp-facture-electronique-fr   ← Länderadapter (FR)
  ├── PAConfig(OAuthConfig)
  ├── FlowClient(BaseEInvoicingClient)      ← OAuth2, XP Z12-013 Annex A
  ├── DirectoryClient(BaseEInvoicingClient) ← OAuth2, XP Z12-013 Annex B
  └── FrLifecycleManager(BaseLifecycleManager)

mcp-fattura-elettronica-it    ← Länderadapter (IT)
  ├── ItalyPartyValidator(BasePartyValidator)   ← Partita IVA Modulo-10
  ├── FatturaGenerator(BaseDocumentGenerator)   ← FatturaPA XML v1.6.1
  ├── FatturaValidator(BaseDocumentValidator)   ← lxml XSD v1.6.1
  └── FatturaParser(BaseDocumentParser)         ← lxml xpath
```

## Plugin-Registrierungsmuster

Länderpakete registrieren ihre Tools auf einer gemeinsamen oder eigenständigen FastMCP-Instanz:

```python
# Eigenständig (vorhandene server.py, keine Änderungen erforderlich)
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="…")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# Multi-Länder (optionaler EInvoicingMCPServer)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="…")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

## Kompatibilität mit Claude Desktop / Cursor / Kiro

Bestehende Konfigurationen für `mcp-facture-electronique-fr` und `mcp-fattura-elettronica-it`
erfordern **keine Änderungen**: Tool-Namen, Signaturen, Umgebungsvariablen und Einstiegspunkte
(`server:main`) bleiben vollständig erhalten.

## Roadmap-Kompatibilität

Offenes Backlog und Sprint-Planung pro Land stehen in [`context-library/roadmap-2026.md`](../context-library/roadmap-2026.md). Die folgende Tabelle spiegelt die kanonische Trennung der Rechnungsbäume EN 16931 vs. nicht-EN 16931 wider (siehe `CLAUDE.md`).

| Land | Version | Standard | Rechnungsbaum | Transport |
|------|---------|----------|---------------|-----------|
| [🇧🇪 BE](https://github.com/cmendezs/mcp-einvoicing-be) | v0.2.0 veröffentlicht | Peppol BIS 3.0 / PINT-BE | `BEInvoice(EN16931Invoice)` | Peppol-Netzwerk (AS4) |
| [🇫🇷 FR](https://github.com/cmendezs/mcp-facture-electronique-fr) | v0.4.0 veröffentlicht | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | `EN16931Invoice` (Ziel — siehe FR-SC-1) | Hybrid / PPF + PDP |
| [🇩🇪 DE](https://github.com/cmendezs/mcp-einvoicing-de) | v0.3.1 veröffentlicht | ZUGFeRD 2.x / XRechnung 3.x | `ZUGFeRDInvoice(EN16931Invoice)` | Direkt + Peppol-Teilnehmer-Lookup |
| [🇮🇹 IT](https://github.com/cmendezs/mcp-fattura-elettronica-it) | v0.2.5 veröffentlicht | FatturaPA v1.2.x | EN 16931 (italienisches CIUS) | Direkt / SdI |
| [🇵🇱 PL](https://github.com/cmendezs/mcp-ksef-pl) | v0.2.2 veröffentlicht | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | `KSeFInvoice(EN16931Invoice)` | Direkte API + Peppol |
| [🇪🇸 ES](https://github.com/cmendezs/mcp-facturacion-electronica-es) | v0.2.0 veröffentlicht | Factura-e / VeriFactu / SII / FACe | Doppelt: `EN16931Invoice` (Factura-e) + `InvoiceDocument` (VeriFactu, SII) | Direkte API (mTLS / OAuth2) |
| [🇧🇷 BR](https://github.com/cmendezs/mcp-nfe-br) | v0.5.2 veröffentlicht | NF-e / NFC-e (modelo 55/65, Schema 4.00); NFS-e Nacional v1.01 | `BRInvoice(InvoiceDocument)` + `NFSeDocument(InvoiceDocument)` | Direktes mTLS / SEFAZ + Gov.br OAuth2 / ADN |

Länder auf dem Planungsradar (noch nicht gescaffoldet — siehe Abschnitt "New country packages" in [`roadmap-2026.md`](../context-library/roadmap-2026.md)): IN, MX, RO, CO, CL, PE, VN, EG, HU, GR, KR, ID, EC, UY (Kategorie 1 — voll laufende Clearance); SG, MY, SA, NG, IL, PY, PH (Kategorie 2 — Rollout 2026); UAE, OM, SK, PT, DK, ZA (Kategorie 3 — Übergang oder spät 2026/2027). Freiwillige EU/APAC/NA-Jurisdiktionen sind Kategorie 4.

## Architekturhinweise

### Transportschnittstelle

Mit zunehmender Anzahl von Adaptern wird eine `TransportInterface`-Abstraktion im Core Duplizierung über Länder hinweg verhindern, die dieselbe Transportschicht nutzen. Aktuelle Adapter-Abdeckung:

| Transport | Länder |
|-----------|--------|
| **Direkte API** (Clearance / Reporting / B2G) | FR (Chorus Pro + PDP/PPF), ES (AEAT + FACe), PL (KSeF), IT (SdI geplant) |
| **mTLS zu Behörden-Webservice** | BR (SEFAZ), ES (VeriFactu, SII) |
| **Peppol-Netzwerk (AS4)** | BE, DE (geplant über DE-PEPPOL-1, v0.5.0) |
| **OAuth2 zu Behörden-Hub** | BR (Gov.br ADN für NFS-e Nacional) |

Eine dedizierte `TransportInterface` wird als architektonische Arbeit verfolgt; heute erweitert jeder Länderadapter `BaseEInvoicingClient` direkt mit dem benötigten Auth-Modus (`AuthMode.OAUTH2_CLIENT_CREDENTIALS`, `AuthMode.MTLS`, `AuthMode.BEARER_TOKEN`, `AuthMode.NONE`).

### EN 16931 Wire-Formate

Das Core-Paket liefert `EN16931UBLSerializer`/`EN16931UBLParser` und `EN16931CIISerializer`/`EN16931CIIParser` (seit v1.3.0), damit EU-Länderadapter UBL 2.1- oder CII D16B-Serialisierung nicht neu implementieren. Neue EU-Länderpakete sollten diese Klassen erweitern, statt einen parallelen XML-Stack zu schreiben.

### ViDA / DRR (2030)

Bis Juli 2030 müssen alle nationalen Systeme die EU Digital Reporting Requirements (DRR) für grenzüberschreitende Transaktionen erfüllen. Die Verwendung von **EN 16931** als kanonischer EU-Rechnungswurzel (`EN16931Invoice`) macht die Rechnungshüllen-Seite bereits zukunftssicher: Länderadapter übersetzen `EN16931Invoice` in das lokale Wire-Format, nicht umgekehrt. Der DRR-Übermittlungs-Lifecycle selbst (Echtzeit-Übermittlung strukturierter Transaktionsdaten an ein zentrales EU-Register, Transaktions-ID-Vergabe, grenzüberschreitende 4-Corner-Abstimmung) ist im Core heute nicht modelliert und wird als separater Workstream in [`roadmap-2026.md`](../context-library/roadmap-2026.md) verfolgt; "unterstützt EN 16931 / Peppol" ist nicht gleichbedeutend mit "unterstützt ViDA DRR".

## Weitere MCP-Server für E-Rechnungen

| Land | Server |
|------|--------|
| Belgien | [`mcp-einvoicing-be`](https://github.com/cmendezs/mcp-einvoicing-be) |
| Brasilien | [`mcp-nfe-br`](https://github.com/cmendezs/mcp-nfe-br) |
| Deutschland | [`mcp-einvoicing-de`](https://github.com/cmendezs/mcp-einvoicing-de) |
| Frankreich | [`mcp-facture-electronique-fr`](https://github.com/cmendezs/mcp-facture-electronique-fr) |
| Italien | [`mcp-fattura-elettronica-it`](https://github.com/cmendezs/mcp-fattura-elettronica-it) |
| Polen | [`mcp-ksef-pl`](https://github.com/cmendezs/mcp-ksef-pl) |
| Spanien | [`mcp-facturacion-electronica-es`](https://github.com/cmendezs/mcp-facturacion-electronica-es) |

## Lizenz

Apache 2.0, siehe [LICENSE](LICENSE).
