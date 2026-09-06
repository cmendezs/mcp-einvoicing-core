---
title: Installation
description: mcp-einvoicing-core mit pip installieren.
---

```bash
pip install mcp-einvoicing-core
```

Fuer das Compliance-Audit-Framework (von der CI der Laenderpakete verwendet):

```bash
pip install mcp-einvoicing-core[audit]
```

Fuer die XSLT-2.0/3.0-Schematron-Validierung (`SaxonSchematronValidator` — erforderlich fuer Schematron-Regelwerke mit XPath-2.0+-Konstrukten, z. B. FNFE-MPE Factur-X 1.08 / ZUGFeRD):

```bash
pip install mcp-einvoicing-core[xslt2]
```
