---
title: Instalacao
description: Instalar mcp-einvoicing-core com pip.
---

```bash
pip install mcp-einvoicing-core
```

Para o framework de auditoria de conformidade (utilizado pela CI dos pacotes por pais):

```bash
pip install mcp-einvoicing-core[audit]
```

Para a validacao Schematron XSLT 2.0/3.0 (`SaxonSchematronValidator` — necessario para conjuntos de regras Schematron que usam construcoes XPath 2.0+, ex. FNFE-MPE Factur-X 1.08 / ZUGFeRD):

```bash
pip install mcp-einvoicing-core[xslt2]
```
