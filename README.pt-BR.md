# mcp-einvoicing-core

[English](README.md) | [Francais](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Espanol](README.es.md) | [Portugues (Brasil)](README.pt-BR.md) | [العربية](README.ar.md)

<!-- mcp-name: io.github.cmendezs/mcp-einvoicing-core -->

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-einvoicing-core.svg)](https://pypi.org/project/mcp-einvoicing-core/)[![mcp-einvoicing-core MCP server](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core/badges/score.svg)](https://glama.ai/mcp/servers/cmendezs/mcp-einvoicing-core)

**Topicos:** `mcp` `mcp-server` `e-invoicing` `electronic-invoicing` `python` `fastmcp` `peppol` `en16931` `ubl` `fatturapa` `xp-z12-013` `nfe` `xml` `base-library`

Pacote base para servidores MCP de faturamento eletronico.

Fornece modelos Pydantic compartilhados, uma arvore de fatura EN 16931, serializadores UBL/CII,
um cliente HTTP OAuth2, lookup SMP Peppol, primitivas de assinatura digital e um framework de
auditoria de conformidade para que os pacotes por pais compartilhem uma base comum sem duplicar codigo.

---

## O que este pacote oferece

| Modulo | Conteudo |
|--------|----------|
| `models` | `InvoiceDocument`, `InvoiceParty`, `InvoiceLineItem`, `PartyAddress`, `VATSummary`, `PaymentTerms`, `DocumentValidationResult`, `TaxIdentifier` (validadores de IDs fiscais por pais: IT, FR, DE, BE, ES, PL, BR, AE, SG, MX), `TaxIdValidationResult` |
| `en16931` | `EN16931Invoice`, `EN16931Party`, `EN16931LineItem`, `EN16931Address`, `EN16931Tax`, `EN16931AllowanceCharge`, `EN16931PaymentMeans` |
| `credit_note` | `EN16931CreditNote` (codigos tipo 381/383/384/385), `BillingReference` |
| `ubl_documents` | `BaseUBLDocument` — envelope compartilhado para familias de documentos UBL/Peppol que nao sao fatura (Peppol Ordering, extensoes jurisdicionais); explicitamente fora da arvore `InvoiceDocument`/`EN16931Invoice` |
| `wire_formats` | `EN16931UBLSerializer`, `EN16931UBLParser`, `EN16931CIISerializer`, `EN16931CIIParser`, `UBL_NSMAP`, `CII_NSMAP` |
| `convert` | `Syntax` (UBL, CII), `convert_wire_format` (deteccao automatica da origem, serializacao para o destino) |
| `base_server` | `EInvoicingMCPServer`, `BaseDocumentGenerator`, `BaseDocumentValidator`, `BaseDocumentParser`, `BaseLifecycleManager`, `BasePartyValidator`, `SubmitResult`, `assert_not_read_only`, `scrub` |
| `http_client` | `BaseEInvoicingClient` (OAuth2, mTLS, bearer, API key, nenhum), `OAuthConfig`, `OAuthValues`, `TokenCache`, `AuthMode` |
| `peppol` | `PeppolSMPClient`, `PeppolParticipantId`, `PeppolServiceInfo`, `PeppolLookupResult`, `PeppolEnvironment`, `PEPPOL_BIS_BILLING_30`, `resolve_naptr` (diagnostico de DNS U-NAPTR/SML autonomo) |
| `peppol.tools` | `register_peppol_tools` (plugin FastMCP montavel: lookup de participante, endpoint de servico, diagnostico de DNS, envio AS4, busca no Directory, alem de 8 ferramentas de listas de codigos eDEC), `default_id_adapter`, `IdentifierAdapter` (contrato do adaptador de identificador nacional) |
| `peppol.codelists` | `CodeList`, `CodelistNotConfiguredError`, `load_codelist` e as funcoes de busca eDEC (tipos de documento, processos, esquemas de identificador de participante, perfis de transporte, casos de uso SPIS). Requer `EINVOICING_PEPPOL_CODELIST_DIR`, veja Configuracao abaixo |
| `genericode` | `parse_genericode`, `CodeList`, `CodelistNotConfiguredError` — parser compartilhado OASIS Genericode 1.0 (usado por `peppol.codelists` e `en16931_codelists`) |
| `en16931_codelists` | `en16931_codelist_tools.register_en16931_codelist_tools` (plugin FastMCP montavel: lookup de pais, moeda, ICD, UNCL1001/1153/4461/5305, motivo de desconto/item/encargo, MIME, EAS, VATEX). Requer `EINVOICING_EN16931_CODELIST_DIR`, veja Configuracao abaixo |
| `peppol.directory` | `PeppolDirectoryClient` (busca REST publica no Peppol Directory, sem autenticacao), `PeppolDirectorySearchResult`, `PeppolBusinessCard`, `PeppolBusinessEntity` |
| `peppol.transport` | `AS4MessageEnvelope`, `AS4TransportClient`, `AS4ReceiptHandler`, `PeppolTransmitter`, `AS4Receipt`, `AS4Credentials` (transmissao Peppol AS4 de saida, agora com assinatura real de mensagens WS-Security); `AS4InboundHandler`, `AS4InboundMessage`, `AS4InboundError`, `StandardBusinessDocumentHeader` (receptor AS4 de entrada, papel C3); `sign_as4_message`, `verify_as4_signature` (primitivas WS-Security) |
| `peppol.trust` | `PeppolTrustStore`, `validate_certificate_chain`, `check_revocation`, `verify_smp_signature` — validacao de cadeia/revogacao/assinatura da PKI OpenPeppol. Requer `EINVOICING_PEPPOL_PKI_DIR` (certificados raiz ainda nao publicados pela OpenPeppol nesta versao — apenas a logica, ate que sejam fornecidos) |
| `peppol.reporting` | `parse_eusr`, `parse_tsr`, `validate_eusr`, `validate_tsr` — modelos e validacao dos relatorios de estatisticas de provedor de servico EUSR/TSR do Peppol (XSD + Schematron empacotados, extra opcional `[xslt2]`) |
| `peppol.mls` | `parse_mls`, `validate_mls`, `build_mls` — modelo e validacao do Peppol Message Level Status (MLS) (Schematron empacotado, extra opcional `[xslt2]`) |
| `schematron` | `SchematronValidator` (XSLT 1.0), `SaxonSchematronValidator` (XSLT 2.0/3.0, extra opcional `[xslt2]`), `load_schematron_validator` (factory de selecao automatica), `get_xslt_version`, `BaseStructuredValidator`, `BaseXSDValidator`, `XSDValidator` (validador XSD concreto generico), `BaseJSONValidator`, `ValidationMessage`, `ValidationResult` |
| `schematron_artifacts` | `en16931_base_schematron_validator` (Schematron base CEN EN16931 compilado e empacotado — apenas regras `BR-*`, sem o overlay Peppol; extra opcional `[xslt2]`) |
| `digital_signature` | `BaseDocumentSigner`, `XAdESEPESSigner`, `XAdESSignerConfig`, `XMLDSigSigner`, `XMLDSigSignerConfig`, `CAdESSigner`, `CAdESSignerConfig`, `SelloDigitalSigner`, `SelloDigitalSignerConfig`, `load_certificate_der` |
| `endpoints` | `BaseEnvironmentEndpoints`, `EndpointSet`, `EndpointEnvironment` (roteamento de URL sandbox/producao) |
| `routing` | `RoutingIdentifier` (validadores estaticos: `validate_de_leitweg`), `RoutingIdValidationResult` |
| `profile_registry` | `ProfileEntry`, `ProfileRegistry`, `profile_registry`, `set_profile_registry` |
| `pdf` | `PDFEmbedder` (incorporacao XML em PDF/A-3); `extract(filename=None)` tenta em sequencia os nomes de arquivo canonicos Factur-X/XRechnung/ZUGFeRD, `identify()` le metadados XMP para detectar um PDF hibrido e seu nivel de conformidade |
| `pdf_tools` | `register_pdf_tools` (plugin FastMCP montavel: `identify_and_extract_pdf`), `identify_and_extract_pdf` |
| `qr` | `generate_qr_png_base64` |
| `xml_utils` | `format_amount`, `format_quantity`, `xml_element`, `xml_optional`, `validate_date_iso`, `validate_iban`, `resolve_xml_input`, `mark_untrusted`, `mark_untrusted_fields`, `filter_empty_values`, `format_error` |
| `download_rules` | `DownloadSpec`, `download_artefacts` |
| `testing` | `InvoiceFixtureFactory` (fixtures pytest compartilhadas) |
| `audit_log` | `AuditLog`, `AuditAction`, `get_audit_log` |
| `confirmation` | `ConfirmationGate`, `ConfirmationStore` (gate de validacao humana) |
| `exceptions` | `EInvoicingError`, `ValidationError`, `PartyValidationError`, `XSDValidationError`, `SchematronValidationError`, `DocumentGenerationError`, `AuthenticationError`, `PlatformError` |
| `logging_utils` | `setup_logging`, `get_logger` |
| `audit` | Framework de auditoria de conformidade: `AuditReport`, `CheckResult`, `CheckFinding`, constantes de severidade, `make_report`, `render_summary_table`, `parse_audit_args`, `run_check_core_coverage`, `run_check_version_compatibility`, `run_check_known_shared_helpers`, `TaxRate`, `load_rates` (extra opcional `[audit]`) |

## Pacotes por pais

| Pais | Pacote | Padrao | Escopo | Status de cobertura |
|------|--------|--------|--------|-----------------------|
| 🇧🇪 Belgica | [`mcp-einvoicing-be`](https://github.com/cmendezs/mcp-einvoicing-be) | Peppol BIS 3.0 / PINT-BE | B2B, 1 de janeiro de 2026 | Ativo; regras de overlay especificas do Peppol nao verificadas (apenas EN 16931 base) |
| 🇧🇷 Brasil | [`mcp-nfe-br`](https://github.com/cmendezs/mcp-nfe-br) | NF-e / NFC-e (modelo 55/65, schema 4.00) / NFS-e Nacional | B2B (NF-e) + B2C (NFC-e), ambos obrigatorios desde 2008 | Ativo; reforma tributaria IBS/CBS em andamento ate 2033 |
| 🇫🇷 Franca | [`mcp-facture-electronique-fr`](https://github.com/cmendezs/mcp-facture-electronique-fr) | NF XP Z12-012 / NF XP Z12-013 / Factur-X / UBL 2.1 / CII | B2B, implantacao progressiva a partir de 1 de setembro de 2026 | Ativo |
| 🇩🇪 Alemanha | [`mcp-einvoicing-de`](https://github.com/cmendezs/mcp-einvoicing-de) | ZUGFeRD 2.x / XRechnung 3.x | B2B, progressiva de 2025 a 2028 | Ativo |
| 🇮🇹 Italia | [`mcp-fattura-elettronica-it`](https://github.com/cmendezs/mcp-fattura-elettronica-it) | FatturaPA / SDI | B2G + B2B + B2C, obrigatorio desde 2019 (B2G desde 2014) | Ativo |
| 🇲🇽 Mexico | [`mcp-cfdi-mx`](https://github.com/cmendezs/mcp-cfdi-mx) | CFDI 4.0 / Complemento de Pagos 2.0 | B2B + B2G, obrigatorio em todo o pais | Ativo; transporte de envio ao PAC pendente |
| 🇵🇱 Polonia | [`mcp-ksef-pl`](https://github.com/cmendezs/mcp-ksef-pl) | KSeF FA(3) / FA(2) / Peppol BIS 3.0 | B2B, progressiva de fevereiro de 2026 a janeiro de 2027 | Ativo; fluxo de sessao em lote nao implementado |
| 🇸🇬 Singapura | [`mcp-invoicenow-sg`](https://github.com/cmendezs/mcp-invoicenow-sg) | PINT-SG v1.4.1 / SG Peppol BIS Billing 3.0 | B2B, obrigatorio para empresas registradas no GST a partir de abril de 2026 | Ativo; escopo de validacao limitado aos controles de aceitacao IRAS C5, as regras Schematron de jurisdicao PINT-SG e a validacao base EN 16931 ainda nao estao conectadas |
| 🇪🇸 Espanha | [`mcp-facturacion-electronica-es`](https://github.com/cmendezs/mcp-facturacion-electronica-es) | Factura-e / VeriFactu / SII / FACe | Pendente da Orden Ministerial, prevista para 2026-10-01 | Ativo para VeriFactu/SII; integracao do formato B2B bloqueada ate a Orden Ministerial |
| 🇦🇪 Emirados Arabes Unidos | [`mcp-einvoicing-ae`](https://github.com/cmendezs/mcp-einvoicing-ae) | PINT AE (faturamento + autofaturamento) / Peppol AE TDD | B2B + B2G, piloto voluntario a partir de julho de 2026, obrigatorio para grandes contribuintes a partir de janeiro de 2027 | Ativo; valida apenas o Schematron base CEN EN16931, a camada de jurisdicao PINT AE e a validacao TDD ainda nao estao disponiveis |

## Instalacao

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

## Configuracao

| Variavel | Usada por | Finalidade |
|---|---|---|
| `EINVOICING_PEPPOL_CODELIST_DIR` | `peppol.codelists` (e as ferramentas de listas de codigos em `peppol.tools`) | Diretorio local com sua propria copia das listas de codigos eDEC da OpenPeppol. **Nao incluidas neste pacote**: as listas de codigos eDEC nao possuem concessao de redistribuicao confirmada pela OpenPeppol, entao o core fornece apenas o parser e as ferramentas de busca, nunca os dados em si. Baixe a exportacao "as GeneriCode" de cada artefato (Document Types, Participant Identifier Schemes, Processes, Transport Profiles, SPIS Use Case) em [docs.peppol.eu/edelivery/codelists](https://docs.peppol.eu/edelivery/codelists/index.html) e aponte esta variavel para o diretorio que os contem. Os nomes de arquivo sao reconhecidos por prefixo, entao uma mudanca de versao (ex.: v9.7 para v9.8) nao exige alteracao de codigo. Se nao definida, as ferramentas de listas de codigos retornam um resultado `configured: false` com instrucoes de configuracao, em vez de lancar uma excecao. |
| `EINVOICING_EN16931_CODELIST_DIR` | `en16931_codelists` (e suas ferramentas FastMCP) | Diretorio local com sua propria copia das listas de codigos semanticas EN 16931 da CEF (pais, moeda, ICD, UNCL1001/1153/4461/5305, motivo de desconto/item/encargo, MIME, EAS, VATEX). **Nao incluidas neste pacote**, mesma postura das listas eDEC acima — baixe o pacote de exportacao "as GeneriCode" da pagina de listas de codigos EN 16931 da CEF. Os nomes de arquivo correspondem exatamente (`Country.gc`, sem prefixo de versao). Se nao definida, as ferramentas retornam `configured: false`. |
| `EINVOICING_PEPPOL_PKI_DIR` | `peppol.trust` | Diretorio local com subdiretorios `test/` e `prod/` contendo certificados raiz/intermediarios da CA da PKI OpenPeppol codificados em PEM, para validacao da cadeia de assinatura de mensagens AS4 e de respostas SMP. Ainda nao publicados pela OpenPeppol como dados empacotados em nenhum lugar — as funcoes de confianca retornam `trust_anchors_configured: false` ate que isso seja definido. |
| `EINVOICING_SMP_ALLOWLIST` | `peppol` (`PeppolSMPClient`, `resolve_naptr`) | Sufixos de hostname separados por virgula para estender a lista de permissoes integrada de pontos de acesso Peppol, usada ao validar um hostname SMP resolvido. |

## Arquitetura

Os pacotes por pais herdam das abstracoes do core e registram suas ferramentas em um servidor MCP compartilhado ou independente:

```
mcp-einvoicing-core
  ├── EN16931Invoice / InvoiceDocument  ← modelos de fatura canonicos
  ├── EN16931CreditNote                 ← nota de credito (codigos tipo 381/383/384/385)
  ├── EN16931UBL/CII Serializer/Parser  ← ida e volta de formato wire
  ├── convert_wire_format               ← conversao CII ↔ UBL
  ├── BaseDocumentGenerator/Validator/Parser/LifecycleManager
  ├── BaseEInvoicingClient              ← HTTP assincrono (OAuth2/mTLS/bearer/API key)
  ├── PeppolSMPClient                   ← lookup de participante via SMP/SML
  ├── PeppolTransmitter                 ← transmissao AS4 de saida
  ├── BaseDocumentSigner                ← XAdES-EPES / XMLDSig
  ├── BaseEnvironmentEndpoints          ← roteamento de URL sandbox/producao
  ├── RoutingIdentifier                 ← validacao de IDs de roteamento por pais
  ├── EInvoicingMCPServer               ← registro de plugins sobre FastMCP
  └── Framework de auditoria            ← verificacoes de conformidade por pacote
```

## Padrao de registro de plugins

Os pacotes por pais registram suas ferramentas em uma instancia FastMCP compartilhada ou independente:

```python
# Independente
from fastmcp import FastMCP
mcp = FastMCP(name="mcp-fattura-elettronica-it", instructions="...")
register_header_tools(mcp)
register_body_tools(mcp)
register_global_tools(mcp)

# Multi-pais (EInvoicingMCPServer opcional)
from mcp_einvoicing_core import EInvoicingMCPServer
server = EInvoicingMCPServer(name="mcp-einvoicing-eu", instructions="...")
server.register_plugin(register_header_tools, "it-header")
server.register_plugin(register_flow_tools, "fr-flow")
server.run()
```

O core tambem oferece seu proprio plugin de ferramentas Peppol montavel, para que os pacotes por
pais deixem de reimplementar a busca SMP e o envio AS4. Forneca um adaptador de identificador
nacional (uma pequena funcao que normaliza um numero nacional simples, por exemplo um numero de
IVA, em um identificador de participante Peppol `"<esquema>:<valor>"`):

```python
from mcp_einvoicing_core.peppol.tools import register_peppol_tools

def be_id_adapter(identifier: str) -> str:
    if ":" in identifier:
        return identifier
    return f"0208:{normalize_vat_be(identifier)[2:]}"  # esquema KBO/BCE

server.register_plugin(
    lambda m: register_peppol_tools(m, id_adapter=be_id_adapter), "peppol"
)
```

Isso registra `peppol_lookup_participant`, `peppol_get_service_endpoint`, `resolve_peppol_dns`,
`peppol_send`, `peppol_directory_search` e 8 ferramentas de listas de codigos eDEC da OpenPeppol
(veja Configuracao acima para `EINVOICING_PEPPOL_CODELIST_DIR`, necessaria para as ferramentas de
listas de codigos). Plugins montaveis separados cobrem as listas de codigos semanticas EN 16931
(`en16931_codelist_tools.register_en16931_codelist_tools`), os relatorios Peppol
(`peppol.reporting_tools.register_peppol_reporting_tools`) e o MLS
(`peppol.mls_tools.register_peppol_mls_tools`).

## Compatibilidade com Claude Desktop / Cursor / Kiro

As configuracoes existentes para os pacotes por pais **nao requerem alteracoes**:
nomes de ferramentas, assinaturas, variaveis de ambiente e pontos de entrada
(`server:main`) foram totalmente preservados.

## Licenca

Apache 2.0, consulte [LICENSE](LICENSE).
