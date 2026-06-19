# mcp-einvoicing-core

[English](README.md) | [Francais](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Espanol](README.es.md) | [Portugues (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Temas:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Paquete base para servidores MCP de facturacion electronica.

Proporciona clases base abstractas, modelos Pydantic compartidos, utilidades XML y un cliente HTTP
para que los paquetes por pais (`mcp-facture-electronique-fr`, `mcp-fattura-elettronica-it`, `mcp-nfe-br`, ...)
compartan una base comun sin duplicar codigo.

---

## Contenido del paquete

| Modulo | Contenido | Utilizado por |
|--------|-----------|---------------|
| `models.py` | `InvoiceParty`, `InvoiceLineItem`, `VATSummary`, `PaymentTerms`, `InvoiceDocument`, `DocumentValidationResult` | IT (generacion estructurada de facturas), futuro BE/PL/DE/ES |
| `base_server.py` | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `EInvoicingMCPServer` | Todos los adaptadores por pais |
| `xml_utils.py` | `format_amount`, `format_quantity`, `validate_date_iso`, `validate_iban`, `xml_element`, `xml_optional`, `format_error`, `filter_empty_values` | IT (extraido literalmente), futuros formatos basados en XML |
| `http_client.py` | `TokenCache`, `OAuthConfig`, `BaseEInvoicingClient` (OAuth2 + sin autenticacion) | FR (extraido literalmente), futuros paises basados en API |
| `exceptions.py` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` | Todos los adaptadores por pais |
| `logging_utils.py` | `setup_logging`, `get_logger` | Todos los adaptadores por pais |

## Instalacion

```bash
pip install mcp-einvoicing-core
```

Este paquete **no tiene dependencias especificas de ningun pais**. `lxml` (necesario para la validacion XSD
en IT y futuros paises) lo declara cada paquete de pais individualmente.

## Arquitectura

```
mcp-einvoicing-core           ← este paquete
  ├── BaseDocumentGenerator   ← abstracto: generate(InvoiceDocument) → str
  ├── BaseDocumentValidator   ← abstracto: validate(xml) → DocumentValidationResult
  ├── BaseDocumentParser      ← abstracto: parse(xml) → dict
  ├── BaseLifecycleManager    ← abstracto: submit/search/get_status (HTTP asincrono)
  ├── BasePartyValidator      ← abstracto: validate_seller/buyer/tax_id
  ├── BaseEInvoicingClient    ← concreto: HTTP asincrono + OAuth2/sin auth/token
  ├── InvoiceDocument (Pydantic)  ← modelo de datos compartido
  └── EInvoicingMCPServer     ← registro de plugins sobre FastMCP

mcp-facture-electronique-fr   ← adaptador de pais (FR)
  ├── PAConfig(OAuthConfig)
  ├── FlowClient(BaseEInvoicingClient)      ← OAuth2, XP Z12-013 Annex A
  ├── DirectoryClient(BaseEInvoicingClient) ← OAuth2, XP Z12-013 Annex B
  └── FrLifecycleManager(BaseLifecycleManager)

mcp-fattura-elettronica-it    ← adaptador de pais (IT)
  ├── ItalyPartyValidator(BasePartyValidator)   ← Partita IVA modulo-10
  ├── FatturaGenerator(BaseDocumentGenerator)   ← FatturaPA XML v1.6.1
  ├── FatturaValidator(BaseDocumentValidator)   ← lxml XSD v1.6.1
  └── FatturaParser(BaseDocumentParser)         ← lxml xpath
```

## Patron de registro de plugins

Los paquetes de pais registran sus herramientas en una instancia de FastMCP compartida o independiente:

```python
# Independiente (server.py existente, no requiere cambios)
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="…")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# Multi-pais (EInvoicingMCPServer opcional)
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

| Pais | Estado | Estandar | Transporte | Hereda | Sobreescribe | Gaps conocidos |
|------|--------|----------|------------|--------|--------------|----------------|
| [🇧🇪 BE](https://github.com/cmendezs/mcp-einvoicing-be) | ✅ Listo | Peppol BIS 3.0 | AS4 / Peppol | todas las clases base | `generate()` → UBL 2.1, `validate()` → Schematron EN16931 | Ninguno |
| [🇫🇷 FR](https://github.com/cmendezs/mcp-facture-electronique-fr) | ✅ Listo | XP Z12-013 | Hibrido / hub PPF | `BaseEInvoicingClient`, `BaseLifecycleManager` | `submit_lifecycle_status`, `healthcheck` | Ninguno |
| [🇩🇪 DE](https://github.com/cmendezs/mcp-einvoicing-de) | ✅ Listo | ZUGFeRD / XRechnung | AS4 / Peppol | todas las clases base | `generate()` devuelve bytes PDF (base64) | Ambiguedad en tipo de retorno de `generate()`: `str` vs `bytes` |
| [🇮🇹 IT](https://github.com/cmendezs/mcp-fattura-elettronica-it) | ✅ Listo | FatturaPA v1.6.1 | Directo / SDI | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BasePartyValidator` | todos los metodos abstractos | `to_invoice_document()` aun no implementado |
| [🇵🇱 PL](https://github.com/cmendezs/mcp-ksef-pl) | ✅ Listo | KSeF FA(2) | API directa | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseLifecycleManager` | Flujo de autenticacion de sesion KSeF | Modo de autenticacion `MTLS` aun no implementado |
| [🇪🇸 ES](https://github.com/cmendezs/mcp-facturacion-electronica-es) | ✅ Listo | FACeB2B / FacturaE | API directa | todas las clases base | Autenticacion mTLS | Modo de autenticacion `MTLS` aun no implementado |
| [🇧🇷 BR](https://github.com/cmendezs/mcp-nfe-br) | 🚧 En progreso | NF-e / NFC-e (schema 4.00) | API directa / SEFAZ | `BasePartyValidator` | Validacion CPF/CNPJ | Generacion NF-e/NFC-e e integracion SEFAZ planificadas |
| 🇷🇴 RO | 📋 Pendiente | RO-UBL (EN 16931) | API directa / clearance | `BaseDocumentGenerator`, `BaseLifecycleManager` | Flujo de clearance ANAF | Se necesita variante de `BaseSchematronValidator` |
| 🇬🇷 GR | 📋 Pendiente | myDATA XML | API directa / reporting | `BaseEInvoicingClient`, `BaseLifecycleManager` | Flujo de autenticacion y reporting myDATA | Cliente API myDATA aun no disenado |
| 🇳🇱🇸🇪🇩🇰🇳🇴 Nordicos/NL | 📋 Pendiente | Peppol BIS 3.0 / UBL | AS4 / Peppol | todas las clases base | `generate()` → UBL 2.1, `validate()` → Schematron | Reutiliza la capa de transporte AS4 de BE |
| 🇵🇹 PT | 📋 Pendiente | CIUS-PT + QR Code | Firma / directo | `BaseDocumentGenerator`, `BaseDocumentValidator` | Firma cualificada + inyeccion QR | Integracion de firma cualificada no disenada |

## Notas de arquitectura

### Interfaz de transporte

A medida que crece el numero de adaptadores, una abstraccion `TransportInterface` en core evitara la duplicacion entre paises que comparten la misma capa de transporte:

| Transporte | Paises |
|------------|--------|
| **API directa** (clearance / reporting) | FR, RO, GR, HU |
| **AS4 / red Peppol** | BE, DE, Nordicos/NL |
| **Hibrido / hub** | FR (ruta dual PPF/PDP) |

### Alemania: 80% de reutilizacion desde FR

El mandato de Alemania (activo desde enero de 2025 para recepcion B2B) favorece ampliamente ZUGFeRD/Factur-X, el mismo modelo de XML incrustado en PDF que el perfil frances Factur-X. La logica de generacion y validacion XML de `mcp-facture-electronique-fr` se puede reutilizar con cambios minimos, lo que convierte a DE en el siguiente adaptador de menor esfuerzo despues de BE.

### ViDA / DRR (2030)

Para julio de 2030, todos los sistemas nacionales deberan alinearse con el Requisito de Reporte Digital de la UE para transacciones transfronterizas. Utilizar **EN 16931** como modelo de datos interno `InvoiceDocument` en este paquete base ya prepara el proyecto para el futuro: los adaptadores de pais traducen EN 16931 → formato local, no al reves.

## Licencia

Apache 2.0, consulte [LICENSE](LICENSE).
