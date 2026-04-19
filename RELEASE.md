# Release Notes

## v0.1.0 — 2026-04-18

Initial public release.

### What's included

**Abstract base classes** (`base_server.py`):
- `BaseDocumentGenerator` — generate e-invoice documents from `InvoiceDocument`
- `BaseDocumentValidator` — validate documents against a schema, returning `DocumentValidationResult`
- `BaseDocumentParser` — parse raw XML/bytes into structured dicts or `InvoiceDocument`
- `BaseLifecycleManager` — async submit, status, search, and lifecycle-event operations
- `BasePartyValidator` — validate seller/buyer parties and tax identifiers
- `EInvoicingMCPServer` — thin wrapper around `FastMCP` with plugin registration

**Shared Pydantic v2 models** (`models.py`):
- `TaxIdentifier`, `PartyAddress`, `InvoiceParty`, `InvoiceLineItem`
- `VATSummary`, `PaymentTerms`, `InvoiceDocument`, `DocumentValidationResult`

**XML utilities** (`xml_utils.py`):
- `format_amount`, `format_quantity` — Decimal-safe monetary/quantity formatting
- `validate_date_iso`, `validate_iban` — format validators
- `xml_element`, `xml_optional`, `xml_escape` — XML building helpers
- `format_error`, `filter_empty_values` — dict/response helpers

**HTTP client** (`http_client.py`):
- `BaseEInvoicingClient` — async httpx client with OAuth2 client_credentials, Bearer token, or no-auth modes; automatic token refresh and 401-retry
- `TokenCache` — in-memory token cache with configurable expiry margin
- `AuthMode` — enum (OAUTH2_CLIENT_CREDENTIALS, BEARER_TOKEN, NONE, MTLS†, API_KEY†)
- `OAuthConfig`, `BaseEInvoicingConfig` — pydantic-settings base configs

**Logging utilities** (`logging_utils.py`):
- `setup_logging`, `get_logger` — stderr-based structured logging

### Country packages using this base

| Package | Version | Country |
|---------|---------|---------|
| `mcp-facture-electronique-fr` | v0.2.0 | 🇫🇷 France (AFNOR XP Z12-013) |
| `mcp-fattura-elettronica-it` | v0.2.0 | 🇮🇹 Italy (FatturaPA v1.6.1 / SDI) |

### Known limitations

- MTLS and API_KEY auth modes are stubs (raise `NotImplementedError`)
- `BaseDocumentParser.to_invoice_document()` raises `NotImplementedError` by default
- `BaseLifecycleManager.submit_lifecycle_status()` and `healthcheck()` are stubs
- `lxml` is intentionally excluded — country packages that need XSD validation must declare it as their own dependency
