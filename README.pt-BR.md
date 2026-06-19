# mcp-einvoicing-core

[English](README.md) | [Francais](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Espanol](README.es.md) | [Portugues (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Tópicos:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Pacote base para servidores MCP de faturamento eletrônico.

Fornece classes base abstratas, modelos Pydantic compartilhados, utilitários XML e um cliente HTTP
para que os pacotes específicos por país (`mcp-facture-electronique-fr`, `mcp-fattura-elettronica-it`, `mcp-nfe-br`, ...)
compartilhem uma base comum sem duplicar código.

---

## O que este pacote oferece

| Módulo | Conteúdo | Usado por |
|--------|----------|-----------|
| `models.py` | `InvoiceParty`, `InvoiceLineItem`, `VATSummary`, `PaymentTerms`, `InvoiceDocument`, `DocumentValidationResult` | IT (geração estruturada de faturas), futuro BE/PL/DE/ES |
| `base_server.py` | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `EInvoicingMCPServer` | Todos os adaptadores de país |
| `xml_utils.py` | `format_amount`, `format_quantity`, `validate_date_iso`, `validate_iban`, `xml_element`, `xml_optional`, `format_error`, `filter_empty_values` | IT (extraído literalmente), futuros formatos baseados em XML |
| `http_client.py` | `TokenCache`, `OAuthConfig`, `BaseEInvoicingClient` (OAuth2 + sem autenticação) | FR (extraído literalmente), futuros países baseados em API |
| `exceptions.py` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` | Todos os adaptadores de país |
| `logging_utils.py` | `setup_logging`, `get_logger` | Todos os adaptadores de país |

## Instalação

```bash
pip install mcp-einvoicing-core
```

Este pacote **não possui dependências específicas de país**. `lxml` (necessário para validação XSD
na IT e futuros países) é declarado por cada pacote de país individualmente.

## Arquitetura

```
mcp-einvoicing-core           ← este pacote
  ├── BaseDocumentGenerator   ← abstrato: generate(InvoiceDocument) → str
  ├── BaseDocumentValidator   ← abstrato: validate(xml) → DocumentValidationResult
  ├── BaseDocumentParser      ← abstrato: parse(xml) → dict
  ├── BaseLifecycleManager    ← abstrato: submit/search/get_status (HTTP assíncrono)
  ├── BasePartyValidator      ← abstrato: validate_seller/buyer/tax_id
  ├── BaseEInvoicingClient    ← concreto: HTTP assíncrono + OAuth2/sem autenticação/token
  ├── InvoiceDocument (Pydantic)  ← modelo de dados compartilhado
  └── EInvoicingMCPServer     ← registro de plugins sobre FastMCP

mcp-facture-electronique-fr   ← adaptador de país (FR)
  ├── PAConfig(OAuthConfig)
  ├── FlowClient(BaseEInvoicingClient)      ← OAuth2, XP Z12-013 Anexo A
  ├── DirectoryClient(BaseEInvoicingClient) ← OAuth2, XP Z12-013 Anexo B
  └── FrLifecycleManager(BaseLifecycleManager)

mcp-fattura-elettronica-it    ← adaptador de país (IT)
  ├── ItalyPartyValidator(BasePartyValidator)   ← Partita IVA módulo 10
  ├── FatturaGenerator(BaseDocumentGenerator)   ← FatturaPA XML v1.6.1
  ├── FatturaValidator(BaseDocumentValidator)   ← lxml XSD v1.6.1
  └── FatturaParser(BaseDocumentParser)         ← lxml xpath
```

## Padrão de registro de plugins

Os pacotes de país registram suas ferramentas em uma instância FastMCP compartilhada ou independente:

```python
# Independente (server.py existente, sem alterações necessárias)
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="…")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# Multi-país (EInvoicingMCPServer opcional)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="…")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

## Compatibilidade com Claude Desktop / Cursor / Kiro

As configurações existentes para `mcp-facture-electronique-fr` e `mcp-fattura-elettronica-it`
**não requerem alterações**: nomes de ferramentas, assinaturas, variáveis de ambiente e pontos de entrada
(`server:main`) foram totalmente preservados.

## Compatibilidade com o roadmap

| País | Status | Padrão | Transporte | Herda | Sobrescreve | Lacunas conhecidas |
|------|--------|--------|------------|-------|-------------|-------------------|
| [🇧🇪 BE](https://github.com/cmendezs/mcp-einvoicing-be) | ✅ Concluído | Peppol BIS 3.0 | AS4 / Peppol | todas as classes base | `generate()` → UBL 2.1, `validate()` → Schematron EN16931 | Nenhuma |
| [🇫🇷 FR](https://github.com/cmendezs/mcp-facture-electronique-fr) | ✅ Concluído | XP Z12-013 | Híbrido / PPF hub | `BaseEInvoicingClient`, `BaseLifecycleManager` | `submit_lifecycle_status`, `healthcheck` | Nenhuma |
| [🇩🇪 DE](https://github.com/cmendezs/mcp-einvoicing-de) | ✅ Concluído | ZUGFeRD / XRechnung | AS4 / Peppol | todas as classes base | `generate()` retorna bytes PDF (base64) | Ambiguidade no tipo de retorno de `generate()`: `str` vs `bytes` |
| [🇮🇹 IT](https://github.com/cmendezs/mcp-fattura-elettronica-it) | ✅ Concluído | FatturaPA v1.6.1 | Direto / SDI | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BasePartyValidator` | todos os métodos abstratos | `to_invoice_document()` ainda não implementado |
| [🇵🇱 PL](https://github.com/cmendezs/mcp-ksef-pl) | ✅ Concluído | KSeF FA(2) | API direta | `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseLifecycleManager` | fluxo de autenticação de sessão KSeF | Modo de autenticação `MTLS` ainda não implementado |
| [🇪🇸 ES](https://github.com/cmendezs/mcp-facturacion-electronica-es) | ✅ Concluído | FACeB2B / FacturaE | API direta | todas as classes base | autenticação mTLS | Modo de autenticação `MTLS` ainda não implementado |
| [🇧🇷 BR](https://github.com/cmendezs/mcp-nfe-br) | 🚧 Em andamento | NF-e / NFC-e (schema 4.00) | API direta / SEFAZ | `BasePartyValidator` | validação CPF/CNPJ | Geração de NF-e/NFC-e e integração com SEFAZ planejadas |
| 🇷🇴 RO | 📋 Backlog | RO-UBL (EN 16931) | API direta / clearance | `BaseDocumentGenerator`, `BaseLifecycleManager` | fluxo de clearance ANAF | Variante de `BaseSchematronValidator` necessária |
| 🇬🇷 GR | 📋 Backlog | myDATA XML | API direta / reporting | `BaseEInvoicingClient`, `BaseLifecycleManager` | fluxo de autenticação + reporting myDATA | Cliente de API myDATA ainda não projetado |
| 🇳🇱🇸🇪🇩🇰🇳🇴 Nórdicos/NL | 📋 Backlog | Peppol BIS 3.0 / UBL | AS4 / Peppol | todas as classes base | `generate()` → UBL 2.1, `validate()` → Schematron | Reutiliza a camada de transporte AS4 do BE |
| 🇵🇹 PT | 📋 Backlog | CIUS-PT + QR Code | Assinatura / direto | `BaseDocumentGenerator`, `BaseDocumentValidator` | Assinatura qualificada + injeção de QR | Integração de assinatura qualificada ainda não projetada |

## Notas de arquitetura

### Interface de transporte

Conforme o número de adaptadores cresce, uma abstração `TransportInterface` no core evitará duplicação entre países que compartilham a mesma camada de transporte:

| Transporte | Países |
|------------|--------|
| **API direta** (clearance / reporting) | FR, RO, GR, HU |
| **AS4 / rede Peppol** | BE, DE, Nórdicos/NL |
| **Híbrido / hub** | FR (caminho duplo PPF/PDP) |

### Alemanha: 80% de reutilização a partir da FR

O mandato da Alemanha (ativo desde janeiro de 2025 para recebimento B2B) favorece fortemente ZUGFeRD/Factur-X, o mesmo modelo de XML embutido em PDF utilizado pelo perfil francês Factur-X. A lógica de geração e validação de XML do `mcp-facture-electronique-fr` pode ser reutilizada com alterações mínimas, tornando o DE o adaptador de menor esforço após o BE.

### ViDA / DRR (2030)

Até julho de 2030, todos os sistemas nacionais devem se alinhar ao Requisito de Relatório Digital da UE para transações transfronteiriças. Utilizar **EN 16931** como modelo de dados interno `InvoiceDocument` neste pacote core já prepara o projeto para o futuro: os adaptadores de país traduzem EN 16931 → formato local, e não o contrário.

## Licença

Apache 2.0, consulte [LICENSE](LICENSE).
