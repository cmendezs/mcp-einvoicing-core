---
title: Installation
description: Install mcp-einvoicing-core with pip.
---

```bash
pip install mcp-einvoicing-core
```

For the compliance audit framework (used by country package CI):

```bash
pip install mcp-einvoicing-core[audit]
```

For XSLT 2.0/3.0 Schematron validation (`SaxonSchematronValidator` — needed for Schematron
rule sets using XPath 2.0+ constructs, e.g. FNFE-MPE Factur-X 1.08 / ZUGFeRD):

```bash
pip install mcp-einvoicing-core[xslt2]
```
