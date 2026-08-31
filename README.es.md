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
| `models` | `InvoiceDocument`, `InvoiceParty`, `InvoiceLineItem`, `PartyAddress`, `VATSummary`, `PaymentTerms`, `DocumentValidationResult`, `TaxIdentifier` (validadores de IDs fiscales por pais: IT, FR, DE, BE, ES, PL, BR, AE, SG), `TaxIdValidationResult` |
| `en16931` | `EN16931Invoice`, `EN16931Party`, `EN16931LineItem`, `EN16931Address`, `EN16931Tax`, `EN16931AllowanceCharge`, `EN16931PaymentMeans` |
| `credit_note` | `EN16931CreditNote` (codigos tipo 381/383/384/385), `BillingReference` |
| `ubl_documents` | `BaseUBLDocument` — envoltura compartida para familias de documentos UBL/Peppol no-factura (Peppol Ordering, extensiones jurisdiccionales); explicitamente fuera del arbol `InvoiceDocument`/`EN16931Invoice` |
| `wire_formats` | `EN16931UBLSerializer`, `EN16931UBLParser`, `EN16931CIISerializer`, `EN16931CIIParser`, `UBL_NSMAP`, `CII_NSMAP` |
| `convert` | `Syntax` (UBL, CII), `convert_wire_format` (deteccion automatica del origen, serializacion al destino) |
| `base_server` | `EInvoicingMCPServer`, `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `SubmitResult`, `assert_not_read_only`, `scrub` |
| `http_client` | `BaseEInvoicingClient` (OAuth2, mTLS, bearer, API key, ninguno), `OAuthConfig`, `OAuthValues`, `TokenCache`, `AuthMode` |
| `peppol` | `PeppolSMPClient`, `PeppolParticipantId`, `PeppolServiceInfo`, `PeppolLookupResult`, `PeppolEnvironment`, `PEPPOL_BIS_BILLING_30`, `resolve_naptr` (diagnostico DNS U-NAPTR/SML independiente) |
| `peppol.tools` | `register_peppol_tools` (plugin FastMCP montable: busqueda de participante, endpoint de servicio, diagnostico DNS, envio AS4, busqueda en el Directorio, mas 8 herramientas de listas de codigos eDEC), `default_id_adapter`, `IdentifierAdapter` (contrato del adaptador de identificador nacional) |
| `peppol.codelists` | `CodeList`, `CodelistNotConfiguredError`, `load_codelist` y las funciones de busqueda eDEC (tipos de documento, procesos, esquemas de identificador de participante, perfiles de transporte, casos de uso SPIS). Requiere `EINVOICING_PEPPOL_CODELIST_DIR`, vease Configuracion mas abajo |
| `genericode` | `parse_genericode`, `CodeList`, `CodelistNotConfiguredError` — parser compartido OASIS Genericode 1.0 (usado por `peppol.codelists` y `en16931_codelists`) |
| `en16931_codelists` | `en16931_codelist_tools.register_en16931_codelist_tools` (plugin FastMCP montable: busqueda de pais, moneda, ICD, UNCL1001/1153/4461/5305, motivo de descuento/articulo/cargo, MIME, EAS, VATEX). Requiere `EINVOICING_EN16931_CODELIST_DIR`, vease Configuracion mas abajo |
| `peppol.directory` | `PeppolDirectoryClient` (busqueda REST publica del Peppol Directory, sin autenticacion), `PeppolDirectorySearchResult`, `PeppolBusinessCard`, `PeppolBusinessEntity` |
| `peppol.transport` | `AS4MessageEnvelope`, `AS4TransportClient`, `AS4ReceiptHandler`, `PeppolTransmitter`, `AS4Receipt`, `AS4Credentials` (transmision saliente Peppol AS4, ahora con firma de mensaje WS-Security real); `AS4InboundHandler`, `AS4InboundMessage`, `AS4InboundError`, `StandardBusinessDocumentHeader` (receptor AS4 entrante, rol C3); `sign_as4_message`, `verify_as4_signature` (primitivas WS-Security) |
| `peppol.trust` | `PeppolTrustStore`, `validate_certificate_chain`, `check_revocation`, `verify_smp_signature` — validacion de cadena/revocacion/firma de la PKI de OpenPeppol. Requiere `EINVOICING_PEPPOL_PKI_DIR` (certificados raiz aun no publicados por OpenPeppol a la fecha de esta version — solo logica hasta que se proporcionen) |
| `peppol.reporting` | `parse_eusr`, `parse_tsr`, `validate_eusr`, `validate_tsr` — modelos y validacion de los informes estadisticos de proveedor de servicio EUSR/TSR de Peppol (XSD + Schematron incluidos, extra opcional `[xslt2]`) |
| `peppol.mls` | `parse_mls`, `validate_mls`, `build_mls` — modelo y validacion del Message Level Status (MLS) de Peppol (Schematron incluido, extra opcional `[xslt2]`) |
| `schematron` | `SchematronValidator` (XSLT 1.0), `SaxonSchematronValidator` (XSLT 2.0/3.0, extra opcional `[xslt2]`), `load_schematron_validator` (factory de seleccion automatica), `get_xslt_version`, `BaseStructuredValidator`, `BaseXSDValidator`, `XSDValidator` (validador XSD concreto generico), `BaseJSONValidator`, `ValidationMessage`, `ValidationResult` |
| `schematron_artifacts` | `en16931_base_schematron_validator` (Schematron base CEN EN16931 compilado e incluido — solo reglas `BR-*`, sin el overlay de Peppol; extra opcional `[xslt2]`) |
| `digital_signature` | `BaseDocumentSigner`, `XAdESEPESSigner`, `XAdESSignerConfig`, `XMLDSigSigner`, `XMLDSigSignerConfig` |
| `endpoints` | `BaseEnvironmentEndpoints`, `EndpointSet`, `EndpointEnvironment` (enrutamiento de URL sandbox/produccion) |
| `routing` | `RoutingIdentifier` (validadores estaticos: `validate_de_leitweg`), `RoutingIdValidationResult` |
| `profile_registry` | `ProfileEntry`, `ProfileRegistry`, `profile_registry`, `set_profile_registry` |
| `pdf` | `PDFEmbedder` (incrustacion XML en PDF/A-3); `extract(filename=None)` prueba en orden los nombres de archivo canonicos Factur-X/XRechnung/ZUGFeRD, `identify()` lee metadatos XMP para detectar un PDF hibrido y su nivel de conformidad |
| `pdf_tools` | `register_pdf_tools` (plugin FastMCP montable: `identify_and_extract_pdf`), `identify_and_extract_pdf` |
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
| 🇧🇪 Belgica | [`mcp-einvoicing-be`](https://github.com/cmendezs/mcp-einvoicing-be) | Peppol BIS 3.0 / PINT-BE | B2B, 1 de enero de 2026 | Activo; reglas de overlay especificas de Peppol no verificadas (solo EN 16931 base) |
| 🇧🇷 Brasil | [`mcp-nfe-br`](https://github.com/cmendezs/mcp-nfe-br) | NF-e / NFC-e (modelo 55/65, schema 4.00) / NFS-e Nacional | B2B (NF-e) + B2C (NFC-e), ambos obligatorios desde 2008 | Activo; reforma fiscal IBS/CBS en curso hasta 2033 |
| 🇫🇷 Francia | [`mcp-facture-electronique-fr`](https://github.com/cmendezs/mcp-facture-electronique-fr) | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | B2B, despliegue progresivo desde el 1 de septiembre de 2026 | Activo |
| 🇩🇪 Alemania | [`mcp-einvoicing-de`](https://github.com/cmendezs/mcp-einvoicing-de) | ZUGFeRD 2.x / XRechnung 3.x | B2B, progresivo de 2025 a 2028 | Activo |
| 🇮🇹 Italia | [`mcp-fattura-elettronica-it`](https://github.com/cmendezs/mcp-fattura-elettronica-it) | FatturaPA / SDI | B2G + B2B + B2C, obligatorio desde 2019 (B2G desde 2014) | Activo |
| 🇵🇱 Polonia | [`mcp-ksef-pl`](https://github.com/cmendezs/mcp-ksef-pl) | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | B2B, progresivo de febrero de 2026 a enero de 2027 | Activo; flujo de sesion por lotes no implementado |
| 🇸🇬 Singapur | [`mcp-invoicenow-sg`](https://github.com/cmendezs/mcp-invoicenow-sg) | PINT-SG v1.4.1 / SG Peppol BIS Billing 3.0 | B2B, obligatorio para empresas registradas en GST desde abril de 2026 | Activo; alcance de validacion limitado a los controles de aceptacion IRAS C5, las reglas Schematron de jurisdiccion PINT-SG y la validacion base EN 16931 aun no estan conectadas |
| 🇪🇸 Espana | [`mcp-facturacion-electronica-es`](https://github.com/cmendezs/mcp-facturacion-electronica-es) | Factura-e / VeriFactu / SII / FACe | Pendiente de la Orden Ministerial, prevista para el 2026-10-01 | Activo para VeriFactu/SII; integracion del formato B2B bloqueada a la espera de la Orden Ministerial |
| 🇦🇪 Emiratos Arabes Unidos | [`mcp-einvoicing-ae`](https://github.com/cmendezs/mcp-einvoicing-ae) | PINT AE (facturacion + autofacturacion) / Peppol AE TDD | B2B + B2G, piloto voluntario desde julio de 2026, obligatorio para grandes contribuyentes desde enero de 2027 | Activo; valida unicamente el Schematron base CEN EN16931, la capa de jurisdiccion PINT AE y la validacion TDD aun no estan disponibles |

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

## Configuracion

| Variable | Usada por | Proposito |
|---|---|---|
| `EINVOICING_PEPPOL_CODELIST_DIR` | `peppol.codelists` (y las herramientas de listas de codigos en `peppol.tools`) | Directorio local con su propia copia de las listas de codigos eDEC de OpenPeppol. **No incluidas en este paquete**: las listas de codigos eDEC no cuentan con una concesion de redistribucion confirmada por OpenPeppol, por lo que el core solo proporciona el parser y las herramientas de busqueda, nunca los datos en si. Descargue la exportacion "as GeneriCode" de cada artefacto (Document Types, Participant Identifier Schemes, Processes, Transport Profiles, SPIS Use Case) desde [docs.peppol.eu/edelivery/codelists](https://docs.peppol.eu/edelivery/codelists/index.html) y apunte esta variable al directorio que los contiene. Los nombres de archivo se reconocen por prefijo, por lo que un cambio de version (p. ej. de v9.7 a v9.8) no requiere modificar el codigo. Si no esta configurada, las herramientas de listas de codigos devuelven un resultado `configured: false` con instrucciones de configuracion en lugar de lanzar una excepcion. |
| `EINVOICING_EN16931_CODELIST_DIR` | `en16931_codelists` (y sus herramientas FastMCP) | Directorio local con su propia copia de las listas de codigos semanticas EN 16931 del CEF (pais, moneda, ICD, UNCL1001/1153/4461/5305, motivo de descuento/articulo/cargo, MIME, EAS, VATEX). **No incluidas en este paquete**, misma postura que las listas eDEC anteriores: descargue el paquete de exportacion "as GeneriCode" desde la pagina de listas de codigos EN 16931 del CEF. Los nombres de archivo coinciden exactamente (`Country.gc`, no un nombre con prefijo de version). Si no esta configurada, las herramientas devuelven `configured: false`. |
| `EINVOICING_PEPPOL_PKI_DIR` | `peppol.trust` | Directorio local con subdirectorios `test/` y `prod/` de certificados raiz/intermedios de la CA de la PKI de OpenPeppol codificados en PEM, para la validacion de la cadena de firma de mensajes AS4 y de respuestas SMP. Aun no publicados por OpenPeppol como datos incluidos en ningun sitio: las funciones de confianza reportan `trust_anchors_configured: false` hasta que se configure esta variable. |
| `EINVOICING_SMP_ALLOWLIST` | `peppol` (`PeppolSMPClient`, `resolve_naptr`) | Sufijos de nombre de host separados por comas para ampliar la lista de permitidos integrada de puntos de acceso Peppol, usada al validar un nombre de host SMP resuelto. |

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

El core tambien incluye su propio plugin de herramientas Peppol montable para que los paquetes
por pais dejen de reimplementar la busqueda SMP y el envio AS4. Proporcione un adaptador de
identificador nacional (una pequena funcion que normaliza un numero nacional simple, por ejemplo
un NIF/CIF, en un identificador de participante Peppol `"<esquema>:<valor>"`):

```python
from mcp_einvoicing_core.peppol.tools import register_peppol_tools

def be_id_adapter(identifier: str) -> str:
    if ":" in identifier:
        return identifier
    return f"0208:{normalize_vat_be(identifier)[2:]}"  # esquema KBO/BCE

server.register_plugin(
    lambda m: register_peppol_tools(m, id_adapter=be_id_adapter), "peppol"
)
```

Esto registra `peppol_lookup_participant`, `peppol_get_service_endpoint`, `resolve_peppol_dns`,
`peppol_send`, `peppol_directory_search` y 8 herramientas de listas de codigos eDEC de OpenPeppol
(vease Configuracion mas arriba para `EINVOICING_PEPPOL_CODELIST_DIR`, necesaria para las
herramientas de listas de codigos). Plugins montables independientes cubren las listas de codigos
semanticas EN 16931 (`en16931_codelist_tools.register_en16931_codelist_tools`), los informes de
Peppol (`peppol.reporting_tools.register_peppol_reporting_tools`) y el MLS
(`peppol.mls_tools.register_peppol_mls_tools`).

## Compatibilidad con Claude Desktop / Cursor / Kiro

Las configuraciones existentes para los paquetes por pais **no requieren cambios**:
los nombres de herramientas, firmas, variables de entorno y puntos de entrada
(`server:main`) se conservan completamente.

## Licencia

Apache 2.0, consulte [LICENSE](LICENSE).
