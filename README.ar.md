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

التراكم المفتوح والتخطيط لكل بلد موجودان في [`context-library/roadmap-2026.md`](../context-library/roadmap-2026.md). يعكس الجدول أدناه الفصل القانوني بين أشجار الفواتير وفق EN 16931 وتلك التي ليست وفق EN 16931 (انظر `CLAUDE.md`).

| البلد | الإصدار | المعيار | شجرة الفاتورة | النقل |
|-------|---------|---------|---------------|-------|
| [🇧🇪 BE](https://github.com/cmendezs/mcp-einvoicing-be) | v0.2.0 منشور | Peppol BIS 3.0 / PINT-BE | `BEInvoice(EN16931Invoice)` | شبكة Peppol (AS4) |
| [🇫🇷 FR](https://github.com/cmendezs/mcp-facture-electronique-fr) | v0.4.0 منشور | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | `EN16931Invoice` (الهدف — انظر FR-SC-1) | هجين / PPF + PDP |
| [🇩🇪 DE](https://github.com/cmendezs/mcp-einvoicing-de) | v0.3.1 منشور | ZUGFeRD 2.x / XRechnung 3.x | `ZUGFeRDInvoice(EN16931Invoice)` | مباشر + lookup للمشارك في Peppol |
| [🇮🇹 IT](https://github.com/cmendezs/mcp-fattura-elettronica-it) | v0.2.5 منشور | FatturaPA v1.2.x | EN 16931 (CIUS الإيطالي) | مباشر / SdI |
| [🇵🇱 PL](https://github.com/cmendezs/mcp-ksef-pl) | v0.2.2 منشور | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | `KSeFInvoice(EN16931Invoice)` | API مباشر + Peppol |
| [🇪🇸 ES](https://github.com/cmendezs/mcp-facturacion-electronica-es) | v0.2.0 منشور | Factura-e / VeriFactu / SII / FACe | مزدوج: `EN16931Invoice` (Factura-e) + `InvoiceDocument` (VeriFactu, SII) | API مباشر (mTLS / OAuth2) |
| [🇧🇷 BR](https://github.com/cmendezs/mcp-nfe-br) | v0.5.2 منشور | NF-e / NFC-e (modelo 55/65, schema 4.00); NFS-e Nacional v1.01 | `BRInvoice(InvoiceDocument)` + `NFSeDocument(InvoiceDocument)` | mTLS مباشر / SEFAZ + Gov.br OAuth2 / ADN |

البلدان على رادار التخطيط (لم يتم scaffold لها بعد — انظر قسم "New country packages" في [`roadmap-2026.md`](../context-library/roadmap-2026.md)): IN, MX, RO, CO, CL, PE, VN, EG, HU, GR, KR, ID, EC, UY (الفئة 1 — تصفية تعمل بالكامل)؛ SG, MY, SA, NG, IL, PY, PH (الفئة 2 — قيد النشر في 2026)؛ UAE, OM, SK, PT, DK, ZA (الفئة 3 — مرحلة انتقالية أو أواخر 2026/2027). تخضع الولايات القضائية الطوعية في UE/APAC/NA للفئة 4.

## ملاحظات معمارية

### واجهة النقل

مع تزايد عدد المحولات، سيمنع تجريد `TransportInterface` في الحزمة الأساسية التكرار عبر البلدان التي تتشارك طبقة النقل نفسها. التغطية الحالية للمحولات:

| النقل | البلدان |
|-------|---------|
| **API مباشر** (تصفية / إبلاغ / B2G) | FR (Chorus Pro + PDP/PPF), ES (AEAT + FACe), PL (KSeF), IT (SdI مخطط) |
| **mTLS إلى خدمة ويب حكومية** | BR (SEFAZ), ES (VeriFactu, SII) |
| **شبكة Peppol (AS4)** | BE, DE (مخطط عبر DE-PEPPOL-1, v0.5.0) |
| **OAuth2 إلى محور حكومي** | BR (Gov.br ADN لـ NFS-e Nacional) |

تتم متابعة `TransportInterface` المخصصة كعمل معماري؛ اليوم يقوم كل محول بلد بتوسيع `BaseEInvoicingClient` مباشرة بوضع المصادقة الذي يحتاجه (`AuthMode.OAUTH2_CLIENT_CREDENTIALS`, `AuthMode.MTLS`, `AuthMode.BEARER_TOKEN`, `AuthMode.NONE`).

### تنسيقات wire الخاصة بـ EN 16931

توفر الحزمة الأساسية `EN16931UBLSerializer`/`EN16931UBLParser` و`EN16931CIISerializer`/`EN16931CIIParser` (منذ v1.3.0) حتى لا يعيد محولات البلدان الأوروبية تنفيذ تسلسل UBL 2.1 أو CII D16B. يجب على حزم البلدان الأوروبية الجديدة توسيع هذه الفئات بدلا من كتابة مكدس XML مواز.

### ViDA / DRR (2030)

بحلول يوليو 2030، يجب أن تتوافق جميع الأنظمة الوطنية مع متطلبات الإبلاغ الرقمي (DRR) للاتحاد الأوروبي للمعاملات العابرة للحدود. إن استخدام **EN 16931** كجذر قانوني لفاتورة الاتحاد الأوروبي (`EN16931Invoice`) يجعل جانب غلاف الفاتورة جاهزا للمستقبل: تترجم محولات البلدان `EN16931Invoice` إلى تنسيق wire المحلي، وليس العكس. أما دورة حياة الإرسال الخاصة بـ DRR ذاتها (الإرسال في الوقت الفعلي لبيانات معاملات منظمة إلى سجل مركزي للاتحاد الأوروبي، إصدار معرّفات معاملات، تسوية 4-corner عابرة للحدود) فهي غير مصاغة في الحزمة الأساسية اليوم ويتم تتبعها كمسار عمل منفصل في [`roadmap-2026.md`](../context-library/roadmap-2026.md)؛ يجب عدم مساواة "يدعم EN 16931 / Peppol" بـ "يدعم ViDA DRR".

## الرخصة

Apache 2.0، انظر [LICENSE](LICENSE).
