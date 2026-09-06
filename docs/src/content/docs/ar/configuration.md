---
title: الاعدادات
description: متغيرات البيئة لـ mcp-einvoicing-core.
---

| المتغير | يستخدمه | الغرض |
|---|---|---|
| `EINVOICING_PEPPOL_CODELIST_DIR` | `peppol.codelists` (وادوات قوائم الرموز في `peppol.tools`) | دليل محلي يحتوي على نسختك الخاصة من قوائم رموز OpenPeppol eDEC. **غير مرفقة مع هذه الحزمة**: لا تتوفر قوائم رموز eDEC على تصريح توزيع مؤكد من OpenPeppol، لذا توفر الحزمة الاساسية المحلل وادوات البحث فقط، وليس البيانات نفسها ابدا. قم بتنزيل تصدير "as GeneriCode" لكل قطعة (Document Types، Participant Identifier Schemes، Processes، Transport Profiles، SPIS Use Case) من [docs.peppol.eu/edelivery/codelists](https://docs.peppol.eu/edelivery/codelists/index.html) وقم بتوجيه هذا المتغير الى الدليل الذي يحتويها. يتم التعرف على اسماء الملفات عبر البادئة، لذا فان ترقية الاصدار (مثلا من v9.7 الى v9.8) لا تتطلب اي تغيير في الكود. عند عدم ضبطه، تعيد ادوات قوائم الرموز نتيجة `configured: false` مع تعليمات الاعداد بدلا من رفع استثناء. |
| `EINVOICING_EN16931_CODELIST_DIR` | `en16931_codelists` (وادواتها في FastMCP) | دليل محلي يحتوي على نسختك الخاصة من قوائم رموز EN 16931 الدلالية الصادرة عن CEF (البلد، العملة، ICD، UNCL1001/1153/4461/5305، سبب الخصم/الصنف/الرسم، MIME، EAS، VATEX). **غير مرفقة**، بنفس وضعية قوائم eDEC اعلاه — قم بتنزيل حزمة التصدير "as GeneriCode" من صفحة قوائم رموز EN 16931 الخاصة بـ CEF. اسماء الملفات تتطابق تماما (`Country.gc`، وليس اسما مسبوقا برقم اصدار). عند عدم ضبط هذا المتغير، تعيد الادوات `configured: false`. |
| `EINVOICING_PEPPOL_PKI_DIR` | `peppol.trust` | دليل محلي يحتوي على دليلين فرعيين `test/` و `prod/` لشهادات جهة التصديق الجذرية/الوسيطة الخاصة بـ OpenPeppol PKI بترميز PEM، للتحقق من سلسلة توقيع رسائل AS4 وتوقيع استجابات SMP. لم تُنشر بعد من قبل OpenPeppol كبيانات مرفقة في اي مكان — تعيد دوال الثقة `trust_anchors_configured: false` الى ان يتم ضبط هذا المتغير. |
| `EINVOICING_SMP_ALLOWLIST` | `peppol` (`PeppolSMPClient`، `resolve_naptr`) | لواحق اسماء مضيف مفصولة بفواصل لتوسيع القائمة البيضاء المدمجة لنقاط وصول Peppol المستخدمة عند التحقق من اسم مضيف SMP الذي تم حله. |
