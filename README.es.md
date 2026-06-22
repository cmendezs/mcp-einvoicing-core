# mcp-einvoicing-core

[English](README.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Temas:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Paquete base para servidores MCP de facturación electrónica.

Proporciona clases base abstractas, modelos Pydantic compartidos, utilidades XML y un cliente HTTP
para que los paquetes por país (`mcp-facture-electronique-fr`, `mcp-fattura-elettronica-it`, `mcp-nfe-br`, ...)
compartan una base común sin duplicar código.

---

## Contenido del paquete

| Módulo | Contenido | Utilizado por |
|--------|-----------|---------------|
| `models.py` | `InvoiceParty`, `InvoiceLineItem`, `VATSummary`, `PaymentTerms`, `InvoiceDocument`, `DocumentValidationResult` | IT (generación estructurada de facturas), futuro BE/PL/DE/ES |
| `base_server.py` | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `EInvoicingMCPServer` | Todos los adaptadores por país |
| `xml_utils.py` | `format_amount`, `format_quantity`, `validate_date_iso`, `validate_iban`, `xml_element`, `xml_optional`, `format_error`, `filter_empty_values` | IT (extraído literalmente), futuros formatos basados en XML |
| `http_client.py` | `TokenCache`, `OAuthConfig`, `BaseEInvoicingClient` (OAuth2 + sin autenticación) | FR (extraído literalmente), futuros países basados en API |
| `exceptions.py` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` | Todos los adaptadores por país |
| `logging_utils.py` | `setup_logging`, `get_logger` | Todos los adaptadores por país |

## Instalación

```bash
pip install mcp-einvoicing-core
```

Este paquete **no tiene dependencias específicas de ningún país**. `lxml` (necesario para la validación XSD
en IT y futuros países) lo declara cada paquete de país individualmente.

## Arquitectura

```
mcp-einvoicing-core           ← este paquete
  ├── BaseDocumentGenerator   ← abstracto: generate(InvoiceDocument) → str
  ├── BaseDocumentValidator   ← abstracto: validate(xml) → DocumentValidationResult
  ├── BaseDocumentParser      ← abstracto: parse(xml) → dict
  ├── BaseLifecycleManager    ← abstracto: submit/search/get_status (HTTP asíncrono)
  ├── BasePartyValidator      ← abstracto: validate_seller/buyer/tax_id
  ├── BaseEInvoicingClient    ← concreto: HTTP asíncrono + OAuth2/sin auth/token
  ├── InvoiceDocument (Pydantic)  ← modelo de datos compartido
  └── EInvoicingMCPServer     ← registro de plugins sobre FastMCP

mcp-facture-electronique-fr   ← adaptador de país (FR)
  ├── PAConfig(OAuthConfig)
  ├── FlowClient(BaseEInvoicingClient)      ← OAuth2, XP Z12-013 Annex A
  ├── DirectoryClient(BaseEInvoicingClient) ← OAuth2, XP Z12-013 Annex B
  └── FrLifecycleManager(BaseLifecycleManager)

mcp-fattura-elettronica-it    ← adaptador de país (IT)
  ├── ItalyPartyValidator(BasePartyValidator)   ← Partita IVA modulo-10
  ├── FatturaGenerator(BaseDocumentGenerator)   ← FatturaPA XML v1.6.1
  ├── FatturaValidator(BaseDocumentValidator)   ← lxml XSD v1.6.1
  └── FatturaParser(BaseDocumentParser)         ← lxml xpath
```

## Patrón de registro de plugins

Los paquetes de país registran sus herramientas en una instancia de FastMCP compartida o independiente:

```python
# Independiente (server.py existente, no requiere cambios)
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="…")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# Multi-país (EInvoicingMCPServer opcional)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="…")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

## Compatibilidad con Claude Desktop / Cursor / Kiro

Las configuraciones existentes para `mcp-facture-electronique-fr` y `mcp-fattura-elettronica-it`
**no requieren cambios**: los nombres de herramientas, firmas, variables de entorno y puntos de entrada
(`server:main`) se conservan completamente.

## Compatibilidad con la hoja de ruta

El backlog abierto y la planificación de sprints por país están en [`context-library/roadmap-2026.md`](../context-library/roadmap-2026.md). La tabla siguiente refleja la separación canónica de árboles de factura EN 16931 frente a no EN 16931 (ver `CLAUDE.md`).

| País | Versión | Estándar | Árbol de factura | Transporte |
|------|---------|----------|------------------|------------|
| [🇧🇪 BE](https://github.com/cmendezs/mcp-einvoicing-be) | v0.2.0 publicado | Peppol BIS 3.0 / PINT-BE | `BEInvoice(EN16931Invoice)` | Red Peppol (AS4) |
| [🇫🇷 FR](https://github.com/cmendezs/mcp-facture-electronique-fr) | v0.4.0 publicado | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | `EN16931Invoice` (objetivo — ver FR-SC-1) | Híbrido / PPF + PDP |
| [🇩🇪 DE](https://github.com/cmendezs/mcp-einvoicing-de) | v0.3.1 publicado | ZUGFeRD 2.x / XRechnung 3.x | `ZUGFeRDInvoice(EN16931Invoice)` | Directo + lookup de participante Peppol |
| [🇮🇹 IT](https://github.com/cmendezs/mcp-fattura-elettronica-it) | v0.2.5 publicado | FatturaPA v1.2.x | EN 16931 (CIUS italiano) | Directo / SdI |
| [🇵🇱 PL](https://github.com/cmendezs/mcp-ksef-pl) | v0.2.2 publicado | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | `KSeFInvoice(EN16931Invoice)` | API directa + Peppol |
| [🇪🇸 ES](https://github.com/cmendezs/mcp-facturacion-electronica-es) | v0.2.0 publicado | Factura-e / VeriFactu / SII / FACe | Dual: `EN16931Invoice` (Factura-e) + `InvoiceDocument` (VeriFactu, SII) | API directa (mTLS / OAuth2) |
| [🇧🇷 BR](https://github.com/cmendezs/mcp-nfe-br) | v0.5.2 publicado | NF-e / NFC-e (modelo 55/65, schema 4.00); NFS-e Nacional v1.01 | `BRInvoice(InvoiceDocument)` + `NFSeDocument(InvoiceDocument)` | mTLS directo / SEFAZ + Gov.br OAuth2 / ADN |

Países en el radar de planificación (aún sin scaffolding — ver la sección "New country packages" en [`roadmap-2026.md`](../context-library/roadmap-2026.md)): IN, MX, RO, CO, CL, PE, VN, EG, HU, GR, KR, ID, EC, UY (categoría 1 — clearance plenamente en producción); SG, MY, SA, NG, IL, PY, PH (categoría 2 — despliegue en 2026); UAE, OM, SK, PT, DK, ZA (categoría 3 — transición o final de 2026/2027). Las jurisdicciones UE/APAC/NA voluntarias son de categoría 4.

## Notas de arquitectura

### Interfaz de transporte

A medida que crece el número de adaptadores, una abstracción `TransportInterface` en core evitará la duplicación entre países que comparten la misma capa de transporte. Cobertura actual de adaptadores:

| Transporte | Países |
|------------|--------|
| **API directa** (clearance / reporting / B2G) | FR (Chorus Pro + PDP/PPF), ES (AEAT + FACe), PL (KSeF), IT (SdI planificado) |
| **mTLS hacia webservice gubernamental** | BR (SEFAZ), ES (VeriFactu, SII) |
| **Red Peppol (AS4)** | BE, DE (planificado vía DE-PEPPOL-1, v0.5.0) |
| **OAuth2 hacia hub gubernamental** | BR (Gov.br ADN para NFS-e Nacional) |

Una `TransportInterface` dedicada se rastrea como trabajo arquitectónico; hoy cada adaptador de país extiende directamente `BaseEInvoicingClient` con el modo de autenticación que necesita (`AuthMode.OAUTH2_CLIENT_CREDENTIALS`, `AuthMode.MTLS`, `AuthMode.BEARER_TOKEN`, `AuthMode.NONE`).

### Formatos wire EN 16931

El paquete core entrega `EN16931UBLSerializer`/`EN16931UBLParser` y `EN16931CIISerializer`/`EN16931CIIParser` (desde la v1.3.0) para que los adaptadores de países UE no reimplementen la serialización UBL 2.1 ni CII D16B. Los nuevos paquetes de país UE deben extender estas clases en lugar de escribir una pila XML paralela.

### ViDA / DRR (2030)

Para julio de 2030, todos los sistemas nacionales deberán alinearse con los Digital Reporting Requirements (DRR) de la UE para transacciones transfronterizas. Utilizar **EN 16931** como raíz canónica de factura UE (`EN16931Invoice`) ya prepara el lado del envelope de factura para el futuro: los adaptadores de país traducen `EN16931Invoice` al formato wire local, no al revés. El ciclo de vida de envío de DRR en sí (envío en tiempo real de datos de transacción estructurados a un registro central de la UE, emisión de IDs de transacción, reconciliación 4-corner transfronteriza) no está modelado en core hoy y se rastrea como flujo de trabajo separado en [`roadmap-2026.md`](../context-library/roadmap-2026.md); no equiparar "soporta EN 16931 / Peppol" con "soporta ViDA DRR".

## Otros servidores MCP de facturación electrónica

| País | Servidor |
|------|----------|
| 🇧🇪 Bélgica | [`mcp-einvoicing-be`](https://github.com/cmendezs/mcp-einvoicing-be) |
| 🇧🇷 Brasil | [`mcp-nfe-br`](https://github.com/cmendezs/mcp-nfe-br) |
| 🇫🇷 Francia | [`mcp-facture-electronique-fr`](https://github.com/cmendezs/mcp-facture-electronique-fr) |
| 🇩🇪 Alemania | [`mcp-einvoicing-de`](https://github.com/cmendezs/mcp-einvoicing-de) |
| 🇮🇹 Italia | [`mcp-fattura-elettronica-it`](https://github.com/cmendezs/mcp-fattura-elettronica-it) |
| 🇵🇱 Polonia | [`mcp-ksef-pl`](https://github.com/cmendezs/mcp-ksef-pl) |
| 🇪🇸 España | [`mcp-facturacion-electronica-es`](https://github.com/cmendezs/mcp-facturacion-electronica-es) |

## Licencia

Apache 2.0, consulte [LICENSE](LICENSE).
