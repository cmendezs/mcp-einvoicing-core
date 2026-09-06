---
title: Installation
description: Installer mcp-einvoicing-core avec pip.
---

```bash
pip install mcp-einvoicing-core
```

Pour le framework d'audit de conformite (utilise par la CI des paquets pays) :

```bash
pip install mcp-einvoicing-core[audit]
```

Pour la validation Schematron XSLT 2.0/3.0 (`SaxonSchematronValidator` — necessaire pour les jeux de regles Schematron utilisant des constructions XPath 2.0+, ex. FNFE-MPE Factur-X 1.08 / ZUGFeRD) :

```bash
pip install mcp-einvoicing-core[xslt2]
```
