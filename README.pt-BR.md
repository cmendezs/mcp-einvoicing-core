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

O backlog aberto e o planejamento de sprints por país estão em [`context-library/roadmap-2026.md`](../context-library/roadmap-2026.md). A tabela abaixo reflete a separação canônica de árvores de fatura EN 16931 e não-EN 16931 (ver `CLAUDE.md`).

| País | Versão | Padrão | Árvore de fatura | Transporte |
|------|--------|--------|------------------|------------|
| [🇧🇪 BE](https://github.com/cmendezs/mcp-einvoicing-be) | v0.2.0 publicado | Peppol BIS 3.0 / PINT-BE | `BEInvoice(EN16931Invoice)` | Rede Peppol (AS4) |
| [🇫🇷 FR](https://github.com/cmendezs/mcp-facture-electronique-fr) | v0.4.0 publicado | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | `EN16931Invoice` (alvo — ver FR-SC-1) | Híbrido / PPF + PDP |
| [🇩🇪 DE](https://github.com/cmendezs/mcp-einvoicing-de) | v0.3.1 publicado | ZUGFeRD 2.x / XRechnung 3.x | `ZUGFeRDInvoice(EN16931Invoice)` | Direto + lookup de participante Peppol |
| [🇮🇹 IT](https://github.com/cmendezs/mcp-fattura-elettronica-it) | v0.2.5 publicado | FatturaPA v1.2.x | EN 16931 (CIUS italiano) | Direto / SdI |
| [🇵🇱 PL](https://github.com/cmendezs/mcp-ksef-pl) | v0.2.2 publicado | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | `KSeFInvoice(EN16931Invoice)` | API direta + Peppol |
| [🇪🇸 ES](https://github.com/cmendezs/mcp-facturacion-electronica-es) | v0.2.0 publicado | Factura-e / VeriFactu / SII / FACe | Dupla: `EN16931Invoice` (Factura-e) + `InvoiceDocument` (VeriFactu, SII) | API direta (mTLS / OAuth2) |
| [🇧🇷 BR](https://github.com/cmendezs/mcp-nfe-br) | v0.5.2 publicado | NF-e / NFC-e (modelo 55/65, schema 4.00); NFS-e Nacional v1.01 | `BRInvoice(InvoiceDocument)` + `NFSeDocument(InvoiceDocument)` | mTLS direto / SEFAZ + Gov.br OAuth2 / ADN |

Países no radar de planejamento (ainda não scaffoldados — ver a seção "New country packages" em [`roadmap-2026.md`](../context-library/roadmap-2026.md)): IN, MX, RO, CO, CL, PE, VN, EG, HU, GR, KR, ID, EC, UY (categoria 1 — clearance totalmente em produção); SG, MY, SA, NG, IL, PY, PH (categoria 2 — rollout em 2026); UAE, OM, SK, PT, DK, ZA (categoria 3 — transição ou final de 2026/2027). As jurisdições UE/APAC/AN voluntárias são da categoria 4.

## Notas de arquitetura

### Interface de transporte

Conforme o número de adaptadores cresce, uma abstração `TransportInterface` no core evitará duplicação entre países que compartilham a mesma camada de transporte. Cobertura atual dos adaptadores:

| Transporte | Países |
|------------|--------|
| **API direta** (clearance / reporting / B2G) | FR (Chorus Pro + PDP/PPF), ES (AEAT + FACe), PL (KSeF), IT (SdI planejado) |
| **mTLS para webservice governamental** | BR (SEFAZ), ES (VeriFactu, SII) |
| **Rede Peppol (AS4)** | BE, DE (planejado via DE-PEPPOL-1, v0.5.0) |
| **OAuth2 para hub governamental** | BR (Gov.br ADN para NFS-e Nacional) |

Uma `TransportInterface` dedicada é rastreada como trabalho arquitetural; hoje cada adaptador de país estende diretamente `BaseEInvoicingClient` com o modo de autenticação de que precisa (`AuthMode.OAUTH2_CLIENT_CREDENTIALS`, `AuthMode.MTLS`, `AuthMode.BEARER_TOKEN`, `AuthMode.NONE`).

### Formatos wire EN 16931

O pacote core fornece `EN16931UBLSerializer`/`EN16931UBLParser` e `EN16931CIISerializer`/`EN16931CIIParser` (desde a v1.3.0) para que os adaptadores de países da UE não reimplementem a serialização UBL 2.1 ou CII D16B. Os novos pacotes de país da UE devem estender essas classes em vez de escrever uma pilha XML paralela.

### ViDA / DRR (2030)

Até julho de 2030, todos os sistemas nacionais devem se alinhar aos Digital Reporting Requirements (DRR) da UE para transações transfronteiriças. Utilizar **EN 16931** como raiz canônica de fatura da UE (`EN16931Invoice`) já prepara o lado do envelope de fatura para o futuro: os adaptadores de país traduzem `EN16931Invoice` para o formato wire local, e não o contrário. O próprio ciclo de vida de envio de DRR (envio em tempo real de dados de transação estruturados para um registro central da UE, emissão de IDs de transação, reconciliação 4-corner transfronteiriça) não está modelado no core hoje e é rastreado como workstream separado em [`roadmap-2026.md`](../context-library/roadmap-2026.md); não equiparar "suporta EN 16931 / Peppol" com "suporta ViDA DRR".

## Licença

Apache 2.0, consulte [LICENSE](LICENSE).
