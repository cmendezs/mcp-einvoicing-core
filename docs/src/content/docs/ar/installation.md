---
title: التثبيت
description: تثبيت mcp-einvoicing-core باستخدام pip.
---

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
