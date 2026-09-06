---
title: Installazione
description: Installare mcp-einvoicing-core con pip.
---

```bash
pip install mcp-einvoicing-core
```

Per il framework di audit di conformita (utilizzato dalla CI dei pacchetti per paese):

```bash
pip install mcp-einvoicing-core[audit]
```

Per la validazione Schematron XSLT 2.0/3.0 (`SaxonSchematronValidator` — necessario per i set di regole Schematron che usano costrutti XPath 2.0+, es. FNFE-MPE Factur-X 1.08 / ZUGFeRD):

```bash
pip install mcp-einvoicing-core[xslt2]
```
