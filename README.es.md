# mcp-einvoicing-core

[English](README.md) | [Francais](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Espanol](README.es.md) | [Portugues (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Temas:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Paquete base para servidores MCP de facturacion electronica.

Proporciona modelos Pydantic compartidos, un arbol de factura EN 16931, serializadores UBL/CII,
un cliente HTTP OAuth2, busqueda SMP Peppol, primitivas de firma digital y un framework de
auditoria de cumplimiento para que los paquetes por pais compartan una base comun sin duplicar codigo.

---

## Contenido del paquete

| Modulo | Contenido |
|--------|-----------|
| `models` | `InvoiceDocument`, `InvoiceParty`, `InvoiceLineItem`, `PartyAddress`, `VATSummary`, `PaymentTerms`, `DocumentValidationResult`, `TaxIdentifier` (validadores de IDs fiscales por pais: IT, FR, DE, BE, ES, PL, BR), `TaxIdValidationResult` |
| `en16931` | `EN16931Invoice`, `EN16931Party`, `EN16931LineItem`, `EN16931Address`, `EN16931Tax`, `EN16931AllowanceCharge`, `EN16931PaymentMeans` |
| `credit_note` | `EN16931CreditNote` (codigos tipo 381/383/384/385), `BillingReference` |
| `wire_formats` | `EN16931UBLSerializer`, `EN16931UBLParser`, `EN16931CIISerializer`, `EN16931CIIParser`, `UBL_NSMAP`, `CII_NSMAP` |
| `convert` | `Syntax` (UBL, CII), `convert_wire_format` (deteccion automatica del origen, serializacion al destino) |
| `base_server` | `EInvoicingMCPServer`, `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `SubmitResult`, `assert_not_read_only`, `scrub` |
| `http_client` | `BaseEInvoicingClient` (OAuth2, mTLS, bearer, API key, ninguno), `OAuthConfig`, `OAuthValues`, `TokenCache`, `AuthMode` |
| `peppol` | `PeppolSMPClient`, `PeppolParticipantId`, `PeppolServiceInfo`, `PeppolLookupResult`, `PeppolEnvironment`, `PEPPOL_BIS_BILLING_30` |
| `peppol.transport` | `AS4MessageEnvelope`, `AS4TransportClient`, `AS4ReceiptHandler`, `PeppolTransmitter`, `AS4Receipt`, `AS4Credentials` (transmision saliente Peppol AS4) |
| `schematron` | `SchematronValidator` (XSLT 1.0), `SaxonSchematronValidator` (XSLT 2.0/3.0, extra opcional `[xslt2]`), `load_schematron_validator` (factory de seleccion automatica), `get_xslt_version`, `BaseStructuredValidator`, `BaseXSDValidator`, `BaseJSONValidator`, `ValidationMessage`, `ValidationResult` |
| `schematron_artifacts` | `en16931_base_schematron_validator` (Schematron base CEN EN16931 compilado e incluido — solo reglas `BR-*`, sin el overlay de Peppol; extra opcional `[xslt2]`) |
| `digital_signature` | `BaseDocumentSigner`, `XAdESEPESSigner`, `XAdESSignerConfig`, `XMLDSigSigner`, `XMLDSigSignerConfig` |
| `endpoints` | `BaseEnvironmentEndpoints`, `EndpointSet`, `EndpointEnvironment` (enrutamiento de URL sandbox/produccion) |
| `routing` | `RoutingIdentifier` (validadores estaticos: `validate_de_leitweg`), `RoutingIdValidationResult` |
| `profile_registry` | `ProfileEntry`, `ProfileRegistry`, `profile_registry`, `set_profile_registry` |
| `pdf` | `PDFEmbedder` (incrustacion XML en PDF/A-3) |
| `qr` | `generate_qr_png_base64` |
| `xml_utils` | `format_amount`, `format_quantity`, `xml_element`, `xml_optional`, `validate_date_iso`, `validate_iban`, `resolve_xml_input`, `mark_untrusted`, `mark_untrusted_fields`, `filter_empty_values`, `format_error` |
| `download_rules` | `DownloadSpec`, `download_artefacts` |
| `testing` | `InvoiceFixtureFactory` (fixtures pytest compartidas) |
| `audit_log` | `AuditLog`, `AuditAction`, `get_audit_log` |
| `confirmation` | `ConfirmationGate`, `ConfirmationStore` (puerta de validacion humana) |
| `exceptions` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `SchematronValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` |
| `logging_utils` | `setup_logging`, `get_logger` |
| `audit` | Framework de auditoria de cumplimiento: `AuditReport`, `CheckResult`, `CheckFinding`, constantes de severidad, `make_report`, `render_summary_table`, `parse_audit_args`, `run_check_core_coverage`, `run_check_version_compatibility`, `run_check_known_shared_helpers`, `TaxRate`, `load_rates` (extra opcional `[audit]`) |

## Paquetes por pais

| Pais | Paquete | Estandar | Alcance | Estado de cobertura |
|------|---------|----------|---------|----------------------|
| Francia | [`mcp-facture-electronique-fr`](https://github.com/cmendezs/mcp-facture-electronique-fr) | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | B2B, despliegue progresivo desde el 1 de septiembre de 2026 | Activo |
| Alemania | [`mcp-einvoicing-de`](https://github.com/cmendezs/mcp-einvoicing-de) | ZUGFeRD 2.x / XRechnung 3.x | B2B, progresivo de 2025 a 2028 | Activo |
| Belgica | [`mcp-einvoicing-be`](https://github.com/cmendezs/mcp-einvoicing-be) | Peppol BIS 3.0 / PINT-BE | B2B, 1 de enero de 2026 | Activo; reglas de overlay especificas de Peppol no verificadas (solo EN 16931 base) |
| Italia | [`mcp-fattura-elettronica-it`](https://github.com/cmendezs/mcp-fattura-elettronica-it) | FatturaPA / SDI | B2G + B2B + B2C, obligatorio desde 2019 (B2G desde 2014) | Activo |
| Polonia | [`mcp-ksef-pl`](https://github.com/cmendezs/mcp-ksef-pl) | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | B2B, progresivo de febrero de 2026 a enero de 2027 | Activo; flujo de sesion por lotes no implementado |
| Espana | [`mcp-facturacion-electronica-es`](https://github.com/cmendezs/mcp-facturacion-electronica-es) | Factura-e / VeriFactu / SII / FACe | Pendiente de la Orden Ministerial, prevista para el 2026-10-01 | Activo para VeriFactu/SII; integracion del formato B2B bloqueada a la espera de la Orden Ministerial |
| Brasil | [`mcp-nfe-br`](https://github.com/cmendezs/mcp-nfe-br) | NF-e / NFC-e (modelo 55/65, schema 4.00) / NFS-e Nacional | B2B (NF-e) + B2C (NFC-e), ambos obligatorios desde 2008 | Activo; reforma fiscal IBS/CBS en curso hasta 2033 |

## Instalacion

```bash
pip install mcp-einvoicing-core
```

Para el framework de auditoria de cumplimiento (utilizado por la CI de los paquetes por pais):

```bash
pip install mcp-einvoicing-core[audit]
```

Para la validacion Schematron XSLT 2.0/3.0 (`SaxonSchematronValidator` — necesario para los conjuntos de reglas Schematron que usan construcciones XPath 2.0+, ej. FNFE-MPE Factur-X 1.08 / ZUGFeRD):

```bash
pip install mcp-einvoicing-core[xslt2]
```

## Arquitectura

Los paquetes por pais heredan de las abstracciones del core y registran sus herramientas en un servidor MCP compartido o independiente:

```
mcp-einvoicing-core
  ├── EN16931Invoice / InvoiceDocument  ← modelos de factura canonicos
  ├── EN16931CreditNote                 ← nota de credito (codigos tipo 381/383/384/385)
  ├── EN16931UBL/CII Serializer/Parser  ← ida y vuelta de formato wire
  ├── convert_wire_format               ← conversion CII ↔ UBL
  ├── BaseDocumentGenerator/Validator/Parser/LifecycleManager
  ├── BaseEInvoicingClient              ← HTTP asincrono (OAuth2/mTLS/bearer/API key)
  ├── PeppolSMPClient                   ← busqueda de participante via SMP/SML
  ├── PeppolTransmitter                 ← transmision AS4 saliente
  ├── BaseDocumentSigner                ← XAdES-EPES / XMLDSig
  ├── BaseEnvironmentEndpoints          ← enrutamiento de URL sandbox/produccion
  ├── RoutingIdentifier                 ← validacion de IDs de enrutamiento por pais
  ├── EInvoicingMCPServer               ← registro de plugins sobre FastMCP
  └── Framework de auditoria            ← controles de cumplimiento por paquete
```

## Patron de registro de plugins

Los paquetes por pais registran sus herramientas en una instancia FastMCP compartida o independiente:

```python
# Independiente
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="...")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# Multi-pais (EInvoicingMCPServer opcional)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="...")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

## Compatibilidad con Claude Desktop / Cursor / Kiro

Las configuraciones existentes para los paquetes por pais **no requieren cambios**:
los nombres de herramientas, firmas, variables de entorno y puntos de entrada
(`server:main`) se conservan completamente.

## Licencia

Apache 2.0, consulte [LICENSE](LICENSE).
