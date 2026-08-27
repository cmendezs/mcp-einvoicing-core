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
| `models` | `InvoiceDocument`, `InvoiceParty`, `InvoiceLineItem`, `PartyAddress`, `VATSummary`, `PaymentTerms`, `DocumentValidationResult`, `TaxIdentifier` (مدققات ارقام ضريبية حسب البلد: IT, FR, DE, BE, ES, PL, BR, AE), `TaxIdValidationResult` |
| `en16931` | `EN16931Invoice`, `EN16931Party`, `EN16931LineItem`, `EN16931Address`, `EN16931Tax`, `EN16931AllowanceCharge`, `EN16931PaymentMeans` |
| `credit_note` | `EN16931CreditNote` (رموز النوع 381/383/384/385), `BillingReference` |
| `ubl_documents` | `BaseUBLDocument` — غلاف مشترك لعائلات مستندات UBL/Peppol غير الفاتورة (Peppol Ordering، امتدادات خاصة بالولاية القضائية)؛ خارج شجرة `InvoiceDocument`/`EN16931Invoice` صراحةً |
| `wire_formats` | `EN16931UBLSerializer`, `EN16931UBLParser`, `EN16931CIISerializer`, `EN16931CIIParser`, `UBL_NSMAP`, `CII_NSMAP` |
| `convert` | `Syntax` (UBL, CII), `convert_wire_format` (كشف تلقائي للمصدر، تسلسل الى الهدف) |
| `base_server` | `EInvoicingMCPServer`, `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `SubmitResult`, `assert_not_read_only`, `scrub` |
| `http_client` | `BaseEInvoicingClient` (OAuth2, mTLS, bearer, مفتاح API, بدون), `OAuthConfig`, `OAuthValues`, `TokenCache`, `AuthMode` |
| `peppol` | `PeppolSMPClient`, `PeppolParticipantId`, `PeppolServiceInfo`, `PeppolLookupResult`, `PeppolEnvironment`, `PEPPOL_BIS_BILLING_30`, `resolve_naptr` (تشخيص DNS مستقل عبر U-NAPTR/SML) |
| `peppol.tools` | `register_peppol_tools` (اضافة FastMCP قابلة للتركيب: بحث عن مشارك، نقطة نهاية خدمة، تشخيص DNS، ارسال AS4، بحث في الدليل، بالاضافة الى 8 ادوات لقوائم رموز eDEC)، `default_id_adapter`، `IdentifierAdapter` (عقد مهايئ المعرف الوطني) |
| `peppol.codelists` | `CodeList`، `CodelistNotConfiguredError`، `load_codelist` ودوال بحث eDEC (انواع المستندات، العمليات، مخططات معرفات المشاركين، ملفات تعريف النقل، حالات استخدام SPIS). يتطلب `EINVOICING_PEPPOL_CODELIST_DIR`، انظر الاعدادات ادناه |
| `genericode` | `parse_genericode`, `CodeList`, `CodelistNotConfiguredError` — محلل OASIS Genericode 1.0 مشترك (يستخدمه `peppol.codelists` و `en16931_codelists`) |
| `en16931_codelists` | `en16931_codelist_tools.register_en16931_codelist_tools` (اضافة FastMCP قابلة للتركيب: بحث عن البلد، العملة، ICD، UNCL1001/1153/4461/5305، سبب الخصم/الصنف/الرسم، MIME، EAS، VATEX). يتطلب `EINVOICING_EN16931_CODELIST_DIR`، انظر الاعدادات ادناه |
| `peppol.directory` | `PeppolDirectoryClient` (بحث REST عام في دليل Peppol، بدون مصادقة)، `PeppolDirectorySearchResult`، `PeppolBusinessCard`، `PeppolBusinessEntity` |
| `peppol.transport` | `AS4MessageEnvelope`, `AS4TransportClient`, `AS4ReceiptHandler`, `PeppolTransmitter`, `AS4Receipt`, `AS4Credentials` (ارسال صادر عبر Peppol AS4، الان مع توقيع رسائل WS-Security حقيقي)؛ `AS4InboundHandler`, `AS4InboundMessage`, `AS4InboundError`, `StandardBusinessDocumentHeader` (مستقبل AS4 وارد، دور C3)؛ `sign_as4_message`, `verify_as4_signature` (بدائيات WS-Security) |
| `peppol.trust` | `PeppolTrustStore`, `validate_certificate_chain`, `check_revocation`, `verify_smp_signature` — التحقق من سلسلة/الغاء/توقيع OpenPeppol PKI. يتطلب `EINVOICING_PEPPOL_PKI_DIR` (الشهادات الجذرية لم تُنشر بعد من قبل OpenPeppol حتى هذا الاصدار — منطق فقط بدون بيانات الى ان تُوفَّر) |
| `peppol.reporting` | `parse_eusr`, `parse_tsr`, `validate_eusr`, `validate_tsr` — نماذج والتحقق من تقارير احصاءات مزودي الخدمة EUSR/TSR الخاصة بـ Peppol (XSD + Schematron مرفقان، اضافة اختيارية `[xslt2]`) |
| `peppol.mls` | `parse_mls`, `validate_mls`, `build_mls` — نموذج والتحقق من حالة مستوى الرسالة (MLS) الخاصة بـ Peppol (Schematron مرفق، اضافة اختيارية `[xslt2]`) |
| `schematron` | `SchematronValidator` (XSLT 1.0), `SaxonSchematronValidator` (XSLT 2.0/3.0، اضافة اختيارية `[xslt2]`)، `load_schematron_validator` (اختيار تلقائي للمحرك)، `get_xslt_version`، `BaseStructuredValidator`، `BaseXSDValidator`، `XSDValidator` (مدقق XSD عام ملموس)، `BaseJSONValidator`، `ValidationMessage`، `ValidationResult` |
| `schematron_artifacts` | `en16931_base_schematron_validator` (شيماترون CEN EN16931 الاساسي المجمع والمرفق — قواعد `BR-*` فقط، بدون تراكب Peppol؛ اضافة اختيارية `[xslt2]`) |
| `digital_signature` | `BaseDocumentSigner`, `XAdESEPESSigner`, `XAdESSignerConfig`, `XMLDSigSigner`, `XMLDSigSignerConfig` |
| `endpoints` | `BaseEnvironmentEndpoints`, `EndpointSet`, `EndpointEnvironment` (توجيه عناوين URL للتجربة/الانتاج) |
| `routing` | `RoutingIdentifier` (مدققات ثابتة: `validate_de_leitweg`), `RoutingIdValidationResult` |
| `profile_registry` | `ProfileEntry`, `ProfileRegistry`, `profile_registry`, `set_profile_registry` |
| `pdf` | `PDFEmbedder` (تضمين XML في PDF/A-3)؛ `extract(filename=None)` يجرب اسماء الملفات القياسية لـ Factur-X/XRechnung/ZUGFeRD بالتتابع، `identify()` يقرا بيانات XMP الوصفية لاكتشاف ملف PDF هجين ومستوى توافقه |
| `pdf_tools` | `register_pdf_tools` (اضافة FastMCP قابلة للتركيب: `identify_and_extract_pdf`)، `identify_and_extract_pdf` |
| `qr` | `generate_qr_png_base64` |
| `xml_utils` | `format_amount`, `format_quantity`, `xml_element`, `xml_optional`, `validate_date_iso`, `validate_iban`, `resolve_xml_input`, `mark_untrusted`, `mark_untrusted_fields`, `filter_empty_values`, `format_error` |
| `download_rules` | `DownloadSpec`, `download_artefacts` |
| `testing` | `InvoiceFixtureFactory` (تجهيزات pytest مشتركة) |
| `audit_log` | `AuditLog`, `AuditAction`, `get_audit_log` |
| `confirmation` | `ConfirmationGate`, `ConfirmationStore` (بوابة تحقق بشري) |
| `exceptions` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `SchematronValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` |
| `logging_utils` | `setup_logging`, `get_logger` |
| `audit` | اطار عمل تدقيق الامتثال: `AuditReport`, `CheckResult`, `CheckFinding`, ثوابت الشدة, `make_report`, `render_summary_table`, `parse_audit_args`, `run_check_core_coverage`, `run_check_version_compatibility`, `run_check_known_shared_helpers`, `TaxRate`, `load_rates` (اضافة اختيارية `[audit]`) |

## حزم البلدان

| البلد | الحزمة | المعيار | النطاق | حالة التغطية |
|-------|--------|---------|--------|----------------|
| 🇧🇪 بلجيكا | [`mcp-einvoicing-be`](https://github.com/cmendezs/mcp-einvoicing-be) | Peppol BIS 3.0 / PINT-BE | B2B، 1 يناير 2026 | نشط؛ قواعد التراكب الخاصة بـ Peppol لم يتم التحقق منها (EN 16931 الاساسي فقط) |
| 🇧🇷 البرازيل | [`mcp-nfe-br`](https://github.com/cmendezs/mcp-nfe-br) | NF-e / NFC-e (modelo 55/65, schema 4.00) / NFS-e Nacional | B2B (NF-e) + B2C (NFC-e)، كلاهما الزامي منذ 2008 | نشط؛ اصلاح ضريبي IBS/CBS جار حتى 2033 |
| 🇫🇷 فرنسا | [`mcp-facture-electronique-fr`](https://github.com/cmendezs/mcp-facture-electronique-fr) | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | B2B، طرح تدريجي اعتبارا من 1 سبتمبر 2026 | نشط |
| 🇩🇪 المانيا | [`mcp-einvoicing-de`](https://github.com/cmendezs/mcp-einvoicing-de) | ZUGFeRD 2.x / XRechnung 3.x | B2B، تدريجي من 2025 الى 2028 | نشط |
| 🇮🇹 ايطاليا | [`mcp-fattura-elettronica-it`](https://github.com/cmendezs/mcp-fattura-elettronica-it) | FatturaPA / SDI | B2G + B2B + B2C، الزامي منذ 2019 (B2G منذ 2014) | نشط |
| 🇵🇱 بولندا | [`mcp-ksef-pl`](https://github.com/cmendezs/mcp-ksef-pl) | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | B2B، تدريجي من فبراير 2026 الى يناير 2027 | نشط؛ تدفق جلسة الدفعات غير مطبق |
| 🇪🇸 اسبانيا | [`mcp-facturacion-electronica-es`](https://github.com/cmendezs/mcp-facturacion-electronica-es) | Factura-e / VeriFactu / SII / FACe | في انتظار Orden Ministerial، المستهدف 2026-10-01 | نشط لـ VeriFactu/SII؛ ربط صيغة B2B معطل بانتظار Orden Ministerial |

## التثبيت

```bash
pip install mcp-einvoicing-core
```

لاطار عمل تدقيق الامتثال (يستخدمه CI لحزم البلدان):

```bash
pip install mcp-einvoicing-core[audit]
```

للتحقق من Schematron باستخدام XSLT 2.0/3.0 (`SaxonSchematronValidator` — ضروري لمجموعات قواعد Schematron التي تستخدم بنى XPath 2.0+، مثل FNFE-MPE Factur-X 1.08 / ZUGFeRD):

```bash
pip install mcp-einvoicing-core[xslt2]
```

## الاعدادات

| المتغير | يستخدمه | الغرض |
|---|---|---|
| `EINVOICING_PEPPOL_CODELIST_DIR` | `peppol.codelists` (وادوات قوائم الرموز في `peppol.tools`) | دليل محلي يحتوي على نسختك الخاصة من قوائم رموز OpenPeppol eDEC. **غير مرفقة مع هذه الحزمة**: لا تتوفر قوائم رموز eDEC على تصريح توزيع مؤكد من OpenPeppol، لذا توفر الحزمة الاساسية المحلل وادوات البحث فقط، وليس البيانات نفسها ابدا. قم بتنزيل تصدير "as GeneriCode" لكل قطعة (Document Types، Participant Identifier Schemes، Processes، Transport Profiles، SPIS Use Case) من [docs.peppol.eu/edelivery/codelists](https://docs.peppol.eu/edelivery/codelists/index.html) وقم بتوجيه هذا المتغير الى الدليل الذي يحتويها. يتم التعرف على اسماء الملفات عبر البادئة، لذا فان ترقية الاصدار (مثلا من v9.7 الى v9.8) لا تتطلب اي تغيير في الكود. عند عدم ضبطه، تعيد ادوات قوائم الرموز نتيجة `configured: false` مع تعليمات الاعداد بدلا من رفع استثناء. |
| `EINVOICING_EN16931_CODELIST_DIR` | `en16931_codelists` (وادواتها في FastMCP) | دليل محلي يحتوي على نسختك الخاصة من قوائم رموز EN 16931 الدلالية الصادرة عن CEF (البلد، العملة، ICD، UNCL1001/1153/4461/5305، سبب الخصم/الصنف/الرسم، MIME، EAS، VATEX). **غير مرفقة**، بنفس وضعية قوائم eDEC اعلاه — قم بتنزيل حزمة التصدير "as GeneriCode" من صفحة قوائم رموز EN 16931 الخاصة بـ CEF. اسماء الملفات تتطابق تماما (`Country.gc`، وليس اسما مسبوقا برقم اصدار). عند عدم ضبط هذا المتغير، تعيد الادوات `configured: false`. |
| `EINVOICING_PEPPOL_PKI_DIR` | `peppol.trust` | دليل محلي يحتوي على دليلين فرعيين `test/` و `prod/` لشهادات جهة التصديق الجذرية/الوسيطة الخاصة بـ OpenPeppol PKI بترميز PEM، للتحقق من سلسلة توقيع رسائل AS4 وتوقيع استجابات SMP. لم تُنشر بعد من قبل OpenPeppol كبيانات مرفقة في اي مكان — تعيد دوال الثقة `trust_anchors_configured: false` الى ان يتم ضبط هذا المتغير. |
| `EINVOICING_SMP_ALLOWLIST` | `peppol` (`PeppolSMPClient`، `resolve_naptr`) | لواحق اسماء مضيف مفصولة بفواصل لتوسيع القائمة البيضاء المدمجة لنقاط وصول Peppol المستخدمة عند التحقق من اسم مضيف SMP الذي تم حله. |

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
  ├── PeppolTransmitter                 ← ارسال صادر عبر AS4
  ├── BaseDocumentSigner                ← XAdES-EPES / XMLDSig
  ├── BaseEnvironmentEndpoints          ← توجيه عناوين URL للتجربة/الانتاج
  ├── RoutingIdentifier                 ← التحقق من معرفات التوجيه حسب البلد
  ├── EInvoicingMCPServer               ← سجل اضافات يغلف FastMCP
  └── اطار عمل التدقيق                  ← فحوصات امتثال لكل حزمة
```

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

توفر الحزمة الاساسية ايضا اضافة ادوات Peppol الخاصة بها القابلة للتركيب حتى تتوقف حزم البلدان
عن اعادة تطبيق بحث SMP وارسال AS4. قم بتوفير مهايئ معرف وطني (دالة صغيرة تحول رقما وطنيا
بسيطا، مثل رقم ضريبة القيمة المضافة، الى معرف مشارك Peppol بصيغة `"<schema>:<value>"`):

```python
from mcp_einvoicing_core.peppol.tools import register_peppol_tools

def be_id_adapter(identifier: str) -> str:
    if ":" in identifier:
        return identifier
    return f"0208:{normalize_vat_be(identifier)[2:]}"  # مخطط KBO/BCE

server.register_plugin(
    lambda m: register_peppol_tools(m, id_adapter=be_id_adapter), "peppol"
)
```

هذا يسجل `peppol_lookup_participant`، `peppol_get_service_endpoint`، `resolve_peppol_dns`،
`peppol_send`، `peppol_directory_search`، بالاضافة الى 8 ادوات لقوائم رموز OpenPeppol eDEC (انظر الاعدادات اعلاه لـ
`EINVOICING_PEPPOL_CODELIST_DIR`، المطلوبة لادوات قوائم الرموز). تغطي اضافات قابلة للتركيب منفصلة قوائم
رموز EN 16931 الدلالية (`en16931_codelist_tools.register_en16931_codelist_tools`)، وتقارير Peppol
(`peppol.reporting_tools.register_peppol_reporting_tools`)، و MLS (`peppol.mls_tools.register_peppol_mls_tools`).

## التوافق مع Claude Desktop / Cursor / Kiro

لا تتطلب الاعدادات الحالية لحزم البلدان **اي تغييرات**:
اسماء الادوات، والتوقيعات، ومتغيرات البيئة، ونقاط الدخول (`server:main`) محفوظة بالكامل.

## الرخصة

Apache 2.0، انظر [LICENSE](LICENSE).
