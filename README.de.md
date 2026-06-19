# mcp-einvoicing-core

[English](README.md) | [Francais](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Espanol](README.es.md) | [Portugues (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Topics:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Basispaket fuer MCP-Server zur elektronischen Rechnungsstellung.

Stellt abstrakte Basisklassen, gemeinsame Pydantic-Modelle, XML-Hilfsfunktionen und einen HTTP-Client bereit,
damit laenderspezifische Pakete (`mcp-facture-electronique-fr`, `mcp-fattura-elettronica-it`, `mcp-nfe-br`, ...)
auf einer gemeinsamen Grundlage aufbauen, ohne Code zu duplizieren.

---

## Was dieses Paket bereitstellt

| Modul | Inhalt | Verwendet von |
|-------|--------|---------------|
| `models.py` | `InvoiceParty`, `InvoiceLineItem`, `VATSummary`, `PaymentTerms`, `InvoiceDocument`, `DocumentValidationResult` | IT (strukturierte Rechnungsgenerierung), zukuenftig BE/PL/DE/ES |
| `base_server.py` | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `EInvoicingMCPServer` | Alle Laenderadapter |
| `xml_utils.py` | `format_amount`, `format_quantity`, `validate_date_iso`, `validate_iban`, `xml_element`, `xml_optional`, `format_error`, `filter_empty_values` | IT (woertlich uebernommen), zukuenftige XML-basierte Formate |
| `http_client.py` | `TokenCache`, `OAuthConfig`, `BaseEInvoicingClient` (OAuth2 + ohne Authentifizierung) | FR (woertlich uebernommen), zukuenftige API-basierte Laender |
| `exceptions.py` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` | Alle Laenderadapter |
| `logging_utils.py` | `setup_logging`, `get_logger` | Alle Laenderadapter |

## Installation

```bash
pip install mcp-einvoicing-core
```

Dieses Paket hat **keine laenderspezifischen Abhaengigkeiten**. `lxml` (fuer die XSD-Validierung
in IT und zukuenftigen Laendern erforderlich) wird von jedem Laenderpaket einzeln deklariert.

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

mcp-facture-electronique-fr   ← Laenderadapter (FR)
  ├── PAConfig(OAuthConfig)
  ├── FlowClient(BaseEInvoicingClient)      ← OAuth2, XP Z12-013 Annex A
  ├── DirectoryClient(BaseEInvoicingClient) ← OAuth2, XP Z12-013 Annex B
  └── FrLifecycleManager(BaseLifecycleManager)

mcp-fattura-elettronica-it    ← Laenderadapter (IT)
  ├── ItalyPartyValidator(BasePartyValidator)   ← Partita IVA Modulo-10
  ├── FatturaGenerator(BaseDocumentGenerator)   ← FatturaPA XML v1.6.1
  ├── FatturaValidator(BaseDocumentValidator)   ← lxml XSD v1.6.1
  └── FatturaParser(BaseDocumentParser)         ← lxml xpath
```

## Plugin-Registrierungsmuster

Laenderpakete registrieren ihre Tools auf einer gemeinsamen oder eigenstaendigen FastMCP-Instanz:

```python
# Eigenstaendig (vorhandene server.py, keine Aenderungen erforderlich)
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="…")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# Multi-Laender (optionaler EInvoicingMCPServer)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="…")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

## Kompatibilitaet mit Claude Desktop / Cursor / Kiro

Bestehende Konfigurationen fuer `mcp-facture-electronique-fr` und `mcp-fattura-elettronica-it`
erfordern **keine Aenderungen**: Tool-Namen, Signaturen, Umgebungsvariablen und Einstiegspunkte
(`server:main`) bleiben vollstaendig erhalten.

## Roadmap-Kompatibilitaet

| Land | Status | Standard | Transport | Erbt | Ueberschreibt | Bekannte Luecken |
|------|--------|----------|-----------|------|----------------|------------------|
| [🇧🇪 BE](https://github.com/cmendezs/mcp-einvoicing-be) | ✅ Fertig | Peppol BIS 3.0 | AS4 / Peppol | Alle Basisklassen | `generate()` → UBL 2.1, `validate()` → Schematron EN16931 | Keine |
| [🇫🇷 FR](https://github.com/cmendezs/mcp-facture-electronique-fr) | ✅ Fertig | XP Z12-013 | Hybrid / PPF-Hub | `BaseEInvoicingClient`, `BaseLifecycleManager` | `submit_lifecycle_status`, `healthcheck` | Keine |
| [🇩🇪 DE](https://github.com/cmendezs/mcp-einvoicing-de) | ✅ Fertig | ZUGFeRD / XRechnung | AS4 / Peppol | Alle Basisklassen | `generate()` gibt PDF-Bytes zurueck (base64) | Rueckgabetyp von `generate()`: Mehrdeutigkeit `str` vs `bytes` |
| [🇮🇹 IT](https://github.com/cmendezs/mcp-fattura-elettronica-it) | ✅ Fertig | FatturaPA v1.6.1 | Direkt / SDI | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BasePartyValidator` | Alle abstrakten Methoden | `to_invoice_document()` noch nicht implementiert |
| [🇵🇱 PL](https://github.com/cmendezs/mcp-ksef-pl) | ✅ Fertig | KSeF FA(2) | Direkte API | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseLifecycleManager` | KSeF-Sitzungsauthentifizierung | `MTLS`-Authentifizierungsmodus noch nicht implementiert |
| [🇪🇸 ES](https://github.com/cmendezs/mcp-facturacion-electronica-es) | ✅ Fertig | FACeB2B / FacturaE | Direkte API | Alle Basisklassen | mTLS-Authentifizierung | `MTLS`-Authentifizierungsmodus noch nicht implementiert |
| [🇧🇷 BR](https://github.com/cmendezs/mcp-nfe-br) | 🚧 In Arbeit | NF-e / NFC-e (Schema 4.00) | Direkte API / SEFAZ | `BasePartyValidator` | CPF/CNPJ-Validierung | NF-e/NFC-e-Generierung und SEFAZ-Integration geplant |
| 🇷🇴 RO | 📋 Backlog | RO-UBL (EN 16931) | Direkte API / Clearance | `BaseDocumentGenerator`, `BaseLifecycleManager` | ANAF-Clearance-Ablauf | `BaseSchematronValidator`-Variante erforderlich |
| 🇬🇷 GR | 📋 Backlog | myDATA XML | Direkte API / Meldung | `BaseEInvoicingClient`, `BaseLifecycleManager` | myDATA-Authentifizierung + Meldeablauf | myDATA-API-Client noch nicht entworfen |
| 🇳🇱🇸🇪🇩🇰🇳🇴 Nordics/NL | 📋 Backlog | Peppol BIS 3.0 / UBL | AS4 / Peppol | Alle Basisklassen | `generate()` → UBL 2.1, `validate()` → Schematron | Verwendet die AS4-Transportschicht von BE wieder |
| 🇵🇹 PT | 📋 Backlog | CIUS-PT + QR-Code | Signatur / direkt | `BaseDocumentGenerator`, `BaseDocumentValidator` | Qualifizierte Signatur + QR-Einbettung | Integration qualifizierter Signaturen noch nicht entworfen |

## Architekturhinweise

### Transportschnittstelle

Mit zunehmender Anzahl von Adaptern wird eine `TransportInterface`-Abstraktion im Core Duplizierung ueber Laender hinweg verhindern, die dieselbe Transportschicht nutzen:

| Transport | Laender |
|-----------|---------|
| **Direkte API** (Clearance / Meldung) | FR, RO, GR, HU |
| **AS4 / Peppol-Netzwerk** | BE, DE, Nordics/NL |
| **Hybrid / Hub** | FR (PPF/PDP-Dualpfad) |

### Deutschland: 80 % Wiederverwendung aus FR

Das deutsche Mandat (seit Januar 2025 fuer B2B-Empfang aktiv) bevorzugt stark ZUGFeRD/Factur-X, das gleiche PDF-eingebettete XML-Modell wie das franzoesische Factur-X-Profil. Die XML-Erzeugungs- und Validierungslogik von `mcp-facture-electronique-fr` kann mit minimalen Aenderungen wiederverwendet werden, wodurch DE nach BE der Adapter mit dem geringsten Aufwand ist.

### ViDA / DRR (2030)

Bis Juli 2030 muessen alle nationalen Systeme die EU Digital Reporting Requirement fuer grenzueberschreitende Transaktionen erfuellen. Die Verwendung von **EN 16931** als internes `InvoiceDocument`-Datenmodell in diesem Core-Paket macht das Projekt bereits zukunftssicher: Laenderadapter uebersetzen EN 16931 → lokales Format, nicht umgekehrt.

## Lizenz

Apache 2.0, siehe [LICENSE](LICENSE).
