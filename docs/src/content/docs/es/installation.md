---
title: Instalacion
description: Instalar mcp-einvoicing-core con pip.
---

```bash
pip install mcp-einvoicing-core
```

Para el framework de auditoria de cumplimiento (utilizado por la CI de los paquetes por pais):

```bash
pip install mcp-einvoicing-core[audit]
```

Para la validacion Schematron XSLT 2.0/3.0 (`SaxonSchematronValidator` — necesario para los conjuntos de reglas Schematron que usan construcciones XPath 2.0+, ej. FNFE-MPE Factur-X 1.08 / ZUGFeRD):

```bash
pip install mcp-einvoicing-core[xslt2]
```
