# mcp-einvoicing-core

[English](README.md) | [Francais](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Espanol](README.es.md) | [Portugues (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**المواضيع:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

الحزمة الأساسية لخوادم MCP الخاصة بالفوترة الإلكترونية.

توفر هذه الحزمة الفئات الأساسية المجردة، ونماذج Pydantic المشتركة، وأدوات XML المساعدة، وعميل HTTP، بحيث تتشارك الحزم الخاصة بكل بلد (`mcp-facture-electronique-fr`، `mcp-fattura-elettronica-it`، `mcp-nfe-br`، ...) أساسا موحدا دون تكرار الكود.

---

## ما توفره هذه الحزمة

| الوحدة | المحتويات | تستخدمها |
|--------|----------|---------|
| `models.py` | `InvoiceParty`, `InvoiceLineItem`, `VATSummary`, `PaymentTerms`, `InvoiceDocument`, `DocumentValidationResult` | IT (إنشاء فواتير منظمة)، مستقبلا BE/PL/DE/ES |
| `base_server.py` | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `EInvoicingMCPServer` | جميع محولات البلدان |
| `xml_utils.py` | `format_amount`, `format_quantity`, `validate_date_iso`, `validate_iban`, `xml_element`, `xml_optional`, `format_error`, `filter_empty_values` | IT (مستخرجة حرفيا)، الصيغ المستقبلية المبنية على XML |
| `http_client.py` | `TokenCache`, `OAuthConfig`, `BaseEInvoicingClient` (OAuth2 + بدون مصادقة) | FR (مستخرجة حرفيا)، البلدان المستقبلية المعتمدة على API |
| `exceptions.py` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` | جميع محولات البلدان |
| `logging_utils.py` | `setup_logging`, `get_logger` | جميع محولات البلدان |

## التثبيت

```bash
pip install mcp-einvoicing-core
```

لا تحتوي هذه الحزمة على **أي تبعيات خاصة ببلد معين**. يتم الإعلان عن `lxml` (المطلوبة للتحقق من صحة XSD في IT والبلدان المستقبلية) بواسطة كل حزمة بلد على حدة.

## البنية المعمارية

```
mcp-einvoicing-core           ← هذه الحزمة
  ├── BaseDocumentGenerator   ← مجرد: generate(InvoiceDocument) → str
  ├── BaseDocumentValidator   ← مجرد: validate(xml) → DocumentValidationResult
  ├── BaseDocumentParser      ← مجرد: parse(xml) → dict
  ├── BaseLifecycleManager    ← مجرد: submit/search/get_status (HTTP غير متزامن)
  ├── BasePartyValidator      ← مجرد: validate_seller/buyer/tax_id
  ├── BaseEInvoicingClient    ← ملموس: HTTP غير متزامن + OAuth2/بدون مصادقة/رمز
  ├── InvoiceDocument (Pydantic)  ← نموذج بيانات مشترك
  └── EInvoicingMCPServer     ← سجل إضافات يغلف FastMCP

mcp-facture-electronique-fr   ← محول بلد (FR)
  ├── PAConfig(OAuthConfig)
  ├── FlowClient(BaseEInvoicingClient)      ← OAuth2, XP Z12-013 الملحق A
  ├── DirectoryClient(BaseEInvoicingClient) ← OAuth2, XP Z12-013 الملحق B
  └── FrLifecycleManager(BaseLifecycleManager)

mcp-fattura-elettronica-it    ← محول بلد (IT)
  ├── ItalyPartyValidator(BasePartyValidator)   ← Partita IVA modulo-10
  ├── FatturaGenerator(BaseDocumentGenerator)   ← FatturaPA XML v1.6.1
  ├── FatturaValidator(BaseDocumentValidator)   ← lxml XSD v1.6.1
  └── FatturaParser(BaseDocumentParser)         ← lxml xpath
```

## نمط تسجيل الإضافات

تسجل حزم البلدان أدواتها على مثيل FastMCP مشترك أو مستقل:

```python
# مستقل (server.py الحالي، لا يتطلب تغييرات)
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="…")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# متعدد البلدان (EInvoicingMCPServer اختياري)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="…")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

## التوافق مع Claude Desktop / Cursor / Kiro

لا تتطلب الإعدادات الحالية لـ `mcp-facture-electronique-fr` و `mcp-fattura-elettronica-it` **أي تغييرات**: أسماء الأدوات، والتوقيعات، ومتغيرات البيئة، ونقاط الدخول (`server:main`) محفوظة بالكامل.

## خريطة التوافق

| البلد | الحالة | المعيار | النقل | يرث | يعيد تعريف | الثغرات المعروفة |
|---------|--------|----------|-----------|----------|-----------|------------|
| [🇧🇪 BE](https://github.com/cmendezs/mcp-einvoicing-be) | ✅ مكتمل | Peppol BIS 3.0 | AS4 / Peppol | جميع الفئات الأساسية | `generate()` → UBL 2.1, `validate()` → Schematron EN16931 | لا يوجد |
| [🇫🇷 FR](https://github.com/cmendezs/mcp-facture-electronique-fr) | ✅ مكتمل | XP Z12-013 | هجين / PPF hub | `BaseEInvoicingClient`, `BaseLifecycleManager` | `submit_lifecycle_status`, `healthcheck` | لا يوجد |
| [🇩🇪 DE](https://github.com/cmendezs/mcp-einvoicing-de) | ✅ مكتمل | ZUGFeRD / XRechnung | AS4 / Peppol | جميع الفئات الأساسية | `generate()` يعيد بايتات PDF (base64) | غموض نوع إرجاع `generate()`: `str` مقابل `bytes` |
| [🇮🇹 IT](https://github.com/cmendezs/mcp-fattura-elettronica-it) | ✅ مكتمل | FatturaPA v1.6.1 | مباشر / SDI | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BasePartyValidator` | جميع الدوال المجردة | `to_invoice_document()` لم يتم تنفيذها بعد |
| [🇵🇱 PL](https://github.com/cmendezs/mcp-ksef-pl) | ✅ مكتمل | KSeF FA(2) | API مباشر | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseLifecycleManager` | تدفق مصادقة جلسة KSeF | وضع مصادقة `MTLS` لم يتم تنفيذه بعد |
| [🇪🇸 ES](https://github.com/cmendezs/mcp-facturacion-electronica-es) | ✅ مكتمل | FACeB2B / FacturaE | API مباشر | جميع الفئات الأساسية | مصادقة mTLS | وضع مصادقة `MTLS` لم يتم تنفيذه بعد |
| [🇧🇷 BR](https://github.com/cmendezs/mcp-nfe-br) | 🚧 قيد التطوير | NF-e / NFC-e (schema 4.00) | API مباشر / SEFAZ | `BasePartyValidator` | التحقق من CPF/CNPJ | إنشاء NF-e/NFC-e وتكامل SEFAZ مخطط لهما |
| 🇷🇴 RO | 📋 قائمة الانتظار | RO-UBL (EN 16931) | API مباشر / تصفية | `BaseDocumentGenerator`, `BaseLifecycleManager` | تدفق تصفية ANAF | مطلوب متغير `BaseSchematronValidator` |
| 🇬🇷 GR | 📋 قائمة الانتظار | myDATA XML | API مباشر / إبلاغ | `BaseEInvoicingClient`, `BaseLifecycleManager` | مصادقة myDATA + تدفق الإبلاغ | عميل myDATA API لم يتم تصميمه بعد |
| 🇳🇱🇸🇪🇩🇰🇳🇴 الشمال/NL | 📋 قائمة الانتظار | Peppol BIS 3.0 / UBL | AS4 / Peppol | جميع الفئات الأساسية | `generate()` → UBL 2.1, `validate()` → Schematron | يعيد استخدام طبقة نقل AS4 من BE |
| 🇵🇹 PT | 📋 قائمة الانتظار | CIUS-PT + QR Code | توقيع / مباشر | `BaseDocumentGenerator`, `BaseDocumentValidator` | توقيع مؤهل + حقن QR | تكامل التوقيع المؤهل لم يتم تصميمه بعد |

## ملاحظات معمارية

### واجهة النقل

مع تزايد عدد المحولات، سيمنع تجريد `TransportInterface` في الحزمة الأساسية التكرار عبر البلدان التي تتشارك طبقة النقل نفسها:

| النقل | البلدان |
|-----------|-----------|
| **API مباشر** (تصفية / إبلاغ) | FR, RO, GR, HU |
| **AS4 / شبكة Peppol** | BE, DE, الشمال/NL |
| **هجين / محور** | FR (مسار PPF/PDP المزدوج) |

### ألمانيا: إعادة استخدام بنسبة 80% من FR

يفضل التفويض الألماني (الساري منذ يناير 2025 لاستقبال B2B) بشكل كبير صيغة ZUGFeRD/Factur-X، وهي نفس نموذج XML المضمن في PDF المستخدم في ملف Factur-X الفرنسي. يمكن إعادة استخدام منطق إنشاء والتحقق من صحة XML في `mcp-facture-electronique-fr` مع تغييرات طفيفة، مما يجعل DE المحول الأقل جهدا بعد BE.

### ViDA / DRR (2030)

بحلول يوليو 2030، يجب أن تتوافق جميع الأنظمة الوطنية مع متطلبات الإبلاغ الرقمي للاتحاد الأوروبي للمعاملات العابرة للحدود. إن استخدام **EN 16931** كنموذج بيانات `InvoiceDocument` الداخلي في هذه الحزمة الأساسية يجعل المشروع جاهزا للمستقبل: تترجم محولات البلدان من EN 16931 إلى الصيغة المحلية، وليس العكس.

## الرخصة

Apache 2.0، انظر [LICENSE](LICENSE).
