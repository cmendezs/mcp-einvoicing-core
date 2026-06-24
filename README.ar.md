# mcp-einvoicing-core

[English](README.md) | [Francais](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Espanol](README.es.md) | [Portugues (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**المواضيع:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

الحزمة الاساسية لخوادم MCP الخاصة بالفوترة الالكترونية.

توفر نماذج Pydantic مشتركة، وشجرة فواتير EN 16931، ومسلسلات UBL/CII،
وعميل HTTP يدعم OAuth2، وبحث SMP في Peppol، وبدائيات توقيع رقمي، واطار عمل
تدقيق امتثال، بحيث تتشارك الحزم الخاصة بكل بلد اساسا موحدا دون تكرار الكود.

---

## ما توفره هذه الحزمة

| الوحدة | المحتويات |
|--------|----------|
| `models` | `InvoiceDocument`, `InvoiceParty`, `InvoiceLineItem`, `PartyAddress`, `VATSummary`, `PaymentTerms`, `DocumentValidationResult`, `TaxIdentifier` (مدققات ارقام ضريبية حسب البلد: IT, FR, DE, BE, ES, PL, BR), `TaxIdValidationResult` |
| `en16931` | `EN16931Invoice`, `EN16931Party`, `EN16931LineItem`, `EN16931Address`, `EN16931Tax`, `EN16931AllowanceCharge`, `EN16931PaymentMeans` |
| `credit_note` | `EN16931CreditNote` (رموز النوع 381/383/384/385), `BillingReference` |
| `wire_formats` | `EN16931UBLSerializer`, `EN16931UBLParser`, `EN16931CIISerializer`, `EN16931CIIParser`, `UBL_NSMAP`, `CII_NSMAP` |
| `convert` | `Syntax` (UBL, CII), `convert_wire_format` (كشف تلقائي للمصدر، تسلسل الى الهدف) |
| `base_server` | `EInvoicingMCPServer`, `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `SubmitResult`, `assert_not_read_only`, `scrub` |
| `http_client` | `BaseEInvoicingClient` (OAuth2, mTLS, bearer, مفتاح API, بدون), `OAuthConfig`, `OAuthValues`, `TokenCache`, `AuthMode` |
| `peppol` | `PeppolSMPClient`, `PeppolParticipantId`, `PeppolServiceInfo`, `PeppolLookupResult`, `PeppolEnvironment`, `PEPPOL_BIS_BILLING_30` |
| `schematron` | `SchematronValidator`, `BaseStructuredValidator`, `BaseXSDValidator`, `BaseJSONValidator`, `ValidationMessage`, `ValidationResult` |
| `digital_signature` | `BaseDocumentSigner`, `XAdESEPESSigner`, `XAdESSignerConfig`, `XMLDSigSigner`, `XMLDSigSignerConfig` |
| `endpoints` | `BaseEnvironmentEndpoints`, `EndpointSet`, `EndpointEnvironment` (توجيه عناوين URL للتجربة/الانتاج) |
| `routing` | `RoutingIdentifier` (مدققات ثابتة: `validate_de_leitweg`), `RoutingIdValidationResult` |
| `profile_registry` | `ProfileEntry`, `ProfileRegistry`, `profile_registry`, `set_profile_registry` |
| `pdf` | `PDFEmbedder` (تضمين XML في PDF/A-3) |
| `qr` | `generate_qr_png_base64` |
| `xml_utils` | `format_amount`, `format_quantity`, `xml_element`, `xml_optional`, `validate_date_iso`, `validate_iban`, `resolve_xml_input`, `mark_untrusted`, `mark_untrusted_fields`, `filter_empty_values`, `format_error` |
| `download_rules` | `DownloadSpec`, `download_artefacts` |
| `testing` | `InvoiceFixtureFactory` (تجهيزات pytest مشتركة) |
| `audit_log` | `AuditLog`, `AuditAction`, `get_audit_log` |
| `confirmation` | `ConfirmationGate`, `ConfirmationStore` (بوابة تحقق بشري) |
| `exceptions` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `SchematronValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` |
| `logging_utils` | `setup_logging`, `get_logger` |
| `audit` | اطار عمل تدقيق الامتثال: `AuditReport`, `CheckResult`, `CheckFinding`, ثوابت الشدة, `make_report`, `render_summary_table`, `parse_audit_args`, `run_check_core_coverage`, `run_check_version_compatibility`, `run_check_known_shared_helpers`, `TaxRate`, `load_rates` (اضافة اختيارية `[audit]`) |

## التثبيت

```bash
pip install mcp-einvoicing-core
```

لاطار عمل تدقيق الامتثال (يستخدمه CI لحزم البلدان):

```bash
pip install mcp-einvoicing-core[audit]
```

## البنية المعمارية

ترث حزم البلدان من تجريدات الحزمة الاساسية وتسجل ادواتها على خادم MCP مشترك او مستقل:

```
mcp-einvoicing-core
  ├── EN16931Invoice / InvoiceDocument  ← نماذج الفاتورة القياسية
  ├── EN16931CreditNote                 ← اشعار دائن (رموز النوع 381/383/384/385)
  ├── EN16931UBL/CII Serializer/Parser  ← ذهاب وعودة لصيغة الاسلاك
  ├── convert_wire_format               ← تحويل CII ↔ UBL
  ├── BaseDocumentGenerator/Validator/Parser/LifecycleManager
  ├── BaseEInvoicingClient              ← HTTP غير متزامن (OAuth2/mTLS/bearer/مفتاح API)
  ├── PeppolSMPClient                   ← بحث عن مشارك عبر SMP/SML
  ├── BaseDocumentSigner                ← XAdES-EPES / XMLDSig
  ├── BaseEnvironmentEndpoints          ← توجيه عناوين URL للتجربة/الانتاج
  ├── RoutingIdentifier                 ← التحقق من معرفات التوجيه حسب البلد
  ├── EInvoicingMCPServer               ← سجل اضافات يغلف FastMCP
  └── اطار عمل التدقيق                  ← فحوصات امتثال لكل حزمة
```

## حزم البلدان

| البلد | الحزمة | المعيار |
|-------|--------|---------|
| فرنسا | [`mcp-facture-electronique-fr`](https://github.com/cmendezs/mcp-facture-electronique-fr) | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII |
| المانيا | [`mcp-einvoicing-de`](https://github.com/cmendezs/mcp-einvoicing-de) | ZUGFeRD 2.x / XRechnung 3.x |
| بلجيكا | [`mcp-einvoicing-be`](https://github.com/cmendezs/mcp-einvoicing-be) | Peppol BIS 3.0 / PINT-BE |
| ايطاليا | [`mcp-fattura-elettronica-it`](https://github.com/cmendezs/mcp-fattura-elettronica-it) | FatturaPA / SDI |
| بولندا | [`mcp-ksef-pl`](https://github.com/cmendezs/mcp-ksef-pl) | KSeF FA(3) / FA(2) / Peppol BIS 3.0 |
| اسبانيا | [`mcp-facturacion-electronica-es`](https://github.com/cmendezs/mcp-facturacion-electronica-es) | Factura-e / VeriFactu / SII / FACe |
| البرازيل | [`mcp-nfe-br`](https://github.com/cmendezs/mcp-nfe-br) | NF-e / NFC-e (modelo 55/65, schema 4.00) / NFS-e Nacional |

## نمط تسجيل الاضافات

تسجل حزم البلدان ادواتها على نسخة FastMCP مشتركة او مستقلة:

```python
# مستقل
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="...")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# متعدد البلدان (EInvoicingMCPServer اختياري)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="...")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

## التوافق مع Claude Desktop / Cursor / Kiro

لا تتطلب الاعدادات الحالية لحزم البلدان **اي تغييرات**:
اسماء الادوات، والتوقيعات، ومتغيرات البيئة، ونقاط الدخول (`server:main`) محفوظة بالكامل.

## الرخصة

Apache 2.0، انظر [LICENSE](LICENSE).
