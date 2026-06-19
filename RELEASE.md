# Release Process

This document describes how to release a new version of `mcp-einvoicing-core` to PyPI.

## One-Time Setup Requirements

### PyPI Trusted Publishing

PyPI publishing is fully automated via OIDC (no token stored). The Trusted Publisher is configured on PyPI under `cmendezs/mcp-einvoicing-core`, workflow `publish.yml`, environment `pypi`. No `.env` or secret needed.

---

## Release Steps

### 1. Bump the version

Edit **both** files — replace `X.X.X` with the new version (e.g. `0.1.0` → `0.1.1`):

- `pyproject.toml` → `version = "X.X.X"`
- `server.json` → `"version": "X.X.X"` and `"version": "X.X.X"` (in `packages[]`)

### 2. Commit, tag and push

GitHub Actions publishes to PyPI automatically on tag push.

```bash
git add pyproject.toml server.json
git commit -m "chore: bump version to X.X.X"
git push origin main
git tag vX.X.X
git push origin vX.X.X
```

---

## Changelog

### [1.7.0] - 2026-06-21
#### Added
- `run_check_known_shared_helpers()` and `KNOWN_SHARED_HELPERS` frozenset: AST-based CHECK 6 that blocks country packages from re-implementing core helpers (compliance audit finding 2.3)
- `load_rates()` and `TaxRate` dataclass: file-driven tax rate loading with citation validation from `specs/rates.toml` (compliance audit finding 4.2)
- 13 new tests in `test_audit.py`

### [1.6.0] - 2026-06-20
#### Added
- `TaxIdentifier.validate_pl_nip()` and `validate_pl_regon()` (Polish NIP modulo-11, REGON 9/14-digit)
- `TaxIdentifier.validate_de_vat()` (German USt-IdNr, DIN ISO/IEC 7064)
- `TaxIdentifier.validate_be_vat()` (Belgian BTW-nummer, modulo-97)
- `TaxIdentifier.validate_es_nif()`, `validate_es_nie()`, `validate_es_cif()` (Spanish NIF/NIE/CIF)
- `TaxIdentifier.validate_fr_siren()` and `validate_fr_siret()` (French INSEE, Luhn checksum)
- `TaxIdentifier.validate_it_codice_fiscale()` (Italian Codice Fiscale, odd/even table + mod-26)
- `caplog` test verifying PKCS#12 wrong-password does not leak password in logs

### [1.5.3] - 2026-06-20
#### Changed
- `BaseDocumentGenerator` is now `Generic[DocumentT]` (bound to `BaseModel`), eliminating Liskov override violations in country packages

### [1.5.2] - 2026-06-20
#### Added
- PEP 561 `py.typed` marker file for proper type information when installing from PyPI
- Fixes mypy "Class cannot subclass Any" errors in downstream country packages CI

### [1.5.1] - 2026-06-15
#### Fixed
- `XMLDSigSigner._build_xmldsig_signed_info` now emits both required `ds:Transform` elements
  (enveloped-signature, then C14N) in `ds:Reference/ds:Transforms`, per MOC 7.0 Table 4-2.
  Previously only the enveloped-signature transform was emitted, causing signed NF-e XML to
  fail `xmldsig-core-schema_v1.01.xsd` validation (`TransformsType` requires exactly 2
  `Transform` elements).
- Added `TestXMLDSigSigner::test_transforms_contains_enveloped_then_c14n` regression test.
- Patch release; no interface change. Required by `mcp-nfe-br` v0.3.0 (`br__sign_nfe`).

### [1.3.0] - 2026-05-30
#### Added
- `EN16931UBLSerializer` — `EN16931Invoice` → UBL 2.1 Invoice / CreditNote XML
- `EN16931UBLParser` — UBL 2.1 Invoice / CreditNote XML → `EN16931Invoice`
- `EN16931CIISerializer` — `EN16931Invoice` → CII CrossIndustryInvoice XML
- `EN16931CIIParser` — CII CrossIndustryInvoice XML → `EN16931Invoice`
- `UBL_NSMAP`, `CII_NSMAP` — namespace constant dicts for country-package extension
- `parse_audit_args` — supporting utility
- All serialisers use `safe_fromstring` (XXE/DoS protection) and `Decimal` rounding with
  EN 16931 rules (ROUND_HALF_UP for line/totals, ROUND_HALF_EVEN for VAT).
- Country packages extend serialisers/parsers via subclass; no core reimplementation required.

### [1.2.0] - 2026-05-21
#### Changed
- `peppol.py` rewritten for full SMP/SML compliance (CORE-PEPPOL-1 through CORE-PEPPOL-7):
  DNS hash switched to Base32-encoded SHA-256 of lowercased `<scheme>:<value>`;
  DNS record type switched from CNAME to U-NAPTR; endpoint URL parsing fixed (`wsa:Address`);
  `transportProfile` now read as XML attribute; `Redirect` support added;
  `[Unverified]` markers removed (spec-confirmed); participant ID length verified per
  OpenPeppol POLICY 7 v4.4.0.
#### Added
- `gaps_registry.toml` for machine-readable `[GAP id=...]` marker tracking.
- `PartyAddress.gln` field (GS1 Global Location Number); required by `mcp-ksef-pl`.

### [1.1.0] - 2026-05
#### Changed / Added (audit-driven hardening)
- `_CORE_MODULES_TO_CHECK` updated to the 13 real sub-modules in `__all__`.
- `_get_mandatory_fields()` replaces static `_CORE_MANDATORY_FIELDS`; derives required fields
  at runtime from `EN16931Invoice.model_fields`.
- CHECK 4 version parsing now uses `packaging.specifiers.SpecifierSet` /
  `packaging.version.Version`.
- `TaxIdentifier.validate_it_partita_iva()` centralised; IT duplicates removed.
- `BaseXSDValidator` / `BaseJSONValidator` added to `schematron.py`.
- `EInvoicingMCPServer` opt-in; FR and IT migrated from bare `FastMCP`.
- `OAuthValues(BaseModel)` + `OAuthConfig(OAuthValues, BaseSettings)` split;
  `BaseEInvoicingClient` accepts `OAuthValues` for multi-country deployments.
- `profile_registry` singleton replaced by `set_profile_registry(registry)`.
- `EN16931Invoice.tax_lines` `min_length=1` moved from `Field()` to `@model_validator`.
- Retry-with-backoff added for 429/503 (`max_retries=3`; exponential 1s/2s/4s, cap 60s).
- `BaseDocumentSigner` ABC with `load_credentials()` and `verify()` abstract methods.
- `BasePartyValidator.validate_tax_id` return type narrowed to `TaxIdValidationResult`.
- `InvoiceParty.alt_tax_ids: list[TaxIdentifier]` replaces `alt_tax_id: Optional[str]`.
- `mcp_einvoicing_core.audit` module; `SubmitResult`; long-lived `httpx.AsyncClient`;
  `rounding_mode` in `format_amount`.

---

## Notes

- PyPI rejects re-uploads of the same version — always bump before tagging.
- GitHub Actions creates the GitHub Release automatically (with release notes) alongside the PyPI publish.
- The `server.json` description field must be **≤ 100 characters**.
