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

### [1.19.0] - 2026-08-21
#### Added
- Peppol tool plugin (`peppol/tools.py`, `register_peppol_tools(mcp, *, id_adapter=None)`), a mountable `ToolRegistrationFn` registering `peppol_lookup_participant`, `peppol_get_service_endpoint`, `resolve_peppol_dns`, `peppol_send` as FastMCP-native tools over `PeppolSMPClient`/`PeppolTransmitter`, plus a national identifier adapter contract (`IdentifierAdapter`, `default_id_adapter`). Absorbs DE's `peppol_check`/`peppol_send` and BE's `check_peppol_participant_be`; both retirements are queued as separate country-package convergence work.
- `resolve_naptr` (`peppol/__init__.py`), a standalone U-NAPTR (SML) DNS diagnostic promoted out of the previously-protected `PeppolSMPClient._resolve_smp_hostname`, which now delegates to it (no behavior change).
- `PDFEmbedder.extract(filename=None)` canonical hybrid-PDF filename fallback (`CANONICAL_HYBRID_PDF_FILENAMES`), absorbing DE's `_ZUGFERD_ATTACHMENT_FILENAMES` loop. Backward compatible: explicit `filename=` keeps returning `bytes | None` unchanged.
- `PDFEmbedder.identify()`, reading XMP metadata to detect Factur-X/ZUGFeRD hybrid PDFs and report conformance level/document type/version. Verified against a real Factur-X 1.09.2 sample XMP supplied under `mcp-einvoicing-de/specs/documentation/zugferd/`.
- Peppol eDEC code list tools (`peppol/codelists.py`): `list_document_type_ids`, `list_process_ids`, `list_participant_id_schemes`, `list_transport_profiles`, `list_spis_use_case_ids`, `check_document_type_id_in_codelist`, `check_process_id_in_codelist`, `check_participant_id_scheme_in_codelist`, `get_peppol_codelist_version`. Data is deliberately not bundled in the wheel: the OpenPeppol eDEC Code Lists carry no confirmed redistribution grant (checked both the file headers and the `docs.peppol.eu/edelivery/codelists/` page text), the identical situation `context-library/decisions/peppol-schematron-artifact.md` in the root repo already found for `PEPPOL-EN16931-UBL.sch`. Each deployment supplies its own local copy via `EINVOICING_PEPPOL_CODELIST_DIR`; every tool returns `configured: false` with setup guidance when unset.
- New `Configuration` section in `README.md` (and all six translated READMEs) documenting `EINVOICING_PEPPOL_CODELIST_DIR` and `EINVOICING_SMP_ALLOWLIST`, plus a Peppol plugin usage example.

#### Fixed
- `PDFEmbedder.embed()` was missing the required `pdfaExtension:schemas` PDF/A-3 extension-schema declaration block (only wrote the `fx:*` value block); now writes both, verified against a real Factur-X sample XMP.
- `identify()`'s block-matching logic fixed to key off the `xmlns:fx=` attribute rather than a namespace-URI substring, since the new extension-schema block also mentions that URI as plain text and would otherwise be matched instead of the real value block.
- `CANONICAL_HYBRID_PDF_FILENAMES` reordered so the two names confirmed against the real "Filename" codelist (`factur-x.xml`, `xrechnung.xml`) try before the two unconfirmed ZUGFeRD 1.x legacy names.
- `check_participant_id_scheme_in_codelist` was matching the codelist's `schemeid` column (a mnemonic, e.g. `BE:EN`) instead of its `iso6523` column (the numeric ICD, e.g. `0208`), caught before shipping.

Not a breaking change; all additions are new symbols/tools, and the one signature change (`PDFEmbedder.extract`'s `filename` parameter accepting `None`) preserves the prior default and return type for every existing call shape.

### [1.18.1] - 2026-08-20
#### Fixed
- `EN16931UBLSerializer._build_root` (`wire_formats.py`) never emitted a top-level `<cbc:DueDate>` (BT-9) — `invoice.due_date` only reached `<cac:PaymentMeans>/<cbc:PaymentDueDate>`, a separate, schema-valid but functionally distinct element. This is not what CEN's `BR-CO-25` checks for (`exists(//cbc:DueDate) or exists(//cac:PaymentTerms/cbc:Note)`), so any EN16931/Peppol invoice with a due date and no `PaymentTerms` note failed `BR-CO-25` regardless of the due date actually being set. Fixed by emitting `<cbc:DueDate>` as a top-level Invoice child, positioned per the UBL 2.1 XSD sequence (`IssueDate` → `IssueTime` → `DueDate` → `InvoiceTypeCode`, confirmed against the vendored `UBL-Invoice-2.1.xsd`). The existing `PaymentMeans/PaymentDueDate` emission is left in place (harmless, schema-valid, not the source of the bug). Surfaced while wiring `[CORE-EN16931-BASE-SCHEMATRON-1]`'s real Schematron validation into `mcp-einvoicing-be`; the CII serializer (`SpecifiedTradePaymentTerms/DueDateDateTime`) was already correct and needed no change. Affects every `EN16931UBLSerializer` consumer: DE, FR, IT, PL, BE. Not a breaking change — the fix only adds a previously-missing, schema-mandated-position element; no existing field or method signature changed.

### [1.18.0] - 2026-08-20
#### Added
- `schematron_artifacts.py`: `en16931_base_schematron_validator()`, a ready-to-use, bundled, compiled CEN EN 16931 base Schematron validator (the `BR-*` rules — structural + arithmetic/totals checks). Compiled from the vendored, EUPL-1.2-licensed `CEN-EN16931-UBL-3.0.20.sch` via SchXslt2 v1.11.2 (MIT), ships inside the wheel under `resources/schematron/en16931_base/` — no compile step at install or call time. Scope is EN16931 base rules only; does NOT include the Peppol-specific overlay (no confirmed OpenPeppol redistribution rights — see `context-library/decisions/peppol-schematron-artifact.md` in the root repo). Reproducible compile step: `scripts/compile_en16931_base_schematron.py`.
- Closes the base-rule portion of `[CORE-PEPPOL-SCHEMATRON-1]` / `mcp-einvoicing-be` BE-SC-11 — see `context-library/roadmap-2026.md` `[CORE-EN16931-BASE-SCHEMATRON-1]`.

### [1.16.2] - 2026-08-09
#### Fixed
- `signer_service.py`'s out-of-process mTLS submit path (`SignerClient.mtls_submit`/`mtls_submit_files` — the recommended path over every country package's legacy in-process fallback) had no 429/503 retry at all, while `BaseEInvoicingClient._request` already did.
- Extracted `BaseEInvoicingClient._retry_delay`'s body into a module-level `compute_retry_delay()` function (plus `DEFAULT_MAX_RETRIES = 3`) in `http_client.py`, so `signer_service.py::_do_mtls_submit` can reuse the same Retry-After/backoff logic without an HTTP client instance; `_retry_delay` now delegates to it (no behavior change for existing callers).
- `_do_mtls_submit` now retries 429/503 up to `DEFAULT_MAX_RETRIES` for both the `files=` (multipart) and `payload_b64=` (raw body) request shapes.
- New `tests/test_signer_service.py` (6 tests, first coverage for `signer_service.py` at all).
- Not a breaking change. `compute_retry_delay` is intentionally not re-exported from `mcp_einvoicing_core/__init__.py` — internal helper.

### [1.16.1] - 2026-08-09
#### Fixed
- `base_server.py::scrub()`: combined IBAN/BIC redaction patterns into a single-pass regex so a redaction placeholder is never re-scanned by the other pattern (was corrupting `"[IBAN REDACTED]"` into `"[IBAN [BIC REDACTED]]"`); made BIC matching case-sensitive (uppercase-only) to stop it matching ordinary 8/11-letter prose words; bounded IBAN space-grouping to real 4-char boundaries. Added `tests/test_scrub.py`.

### [1.16.0] - 2026-08-09
#### Added
- `AuthMode.JWS`: RS256-signed JWT authentication with an `x5c` JOSE header (RFC 7515), for platforms requiring JWS-based auth (first consumer: ES FACe integrator API, `FACe-manual-api-integradores.pdf` §2.3). `BaseEInvoicingClient` mints tokens via `_mint_jws_token()`, routing signing through the existing `SignerClient`/`signer_service.py` isolation pattern when configured, or in-process otherwise.
- `JWSConfig`: Pydantic model for `AuthMode.JWS` configuration.
- `load_certificate_der(cert_path, cert_password=None)`: public helper in `digital_signature.py` returning a certificate's public DER bytes, for country packages building platform-specific auth claims without reaching into private core internals.
- `signer_client.py`/`signer_service.py`: new `sign_jws` operation.
- New dependency: `joserfc>=1.0.0`.

### [1.14.0] - 2026-07-03
#### Added
- `SaxonSchematronValidator`: XSLT 2.0/3.0 Schematron/SVRL backend for `mcp_einvoicing_core.schematron`, using Saxon-HE via the optional `saxonche` extra (`pip install mcp-einvoicing-core[xslt2]`). Resolves DE-XSLT2-1 / FR-XSLT2-1: `SchematronValidator` (lxml/libxslt, XSLT 1.0 only) cannot compile Schematron-derived stylesheets using XPath 2.0+ constructs (`every ... satisfies`, `string-join`, `cast as`), which the FNFE-MPE Factur-X 1.08 / ZUGFeRD rule sets require.
- `get_xslt_version(stylesheet_path)`: reads the `version` attribute off an XSLT stylesheet's root element.
- `load_schematron_validator(stylesheet_path)`: auto-dispatch factory returning `SchematronValidator` for XSLT 1.x or `SaxonSchematronValidator` for 2.x/3.x+, based on the declared version.
- Verified end-to-end against a real bundled Factur-X EN16931 stylesheet and an official AFNOR June-2026 worked example — fixed a UTF-8 BOM decoding bug in the process (several real-world samples carry one; `xml_text=document.decode("utf-8")` left the BOM character in the string, which Saxon rejected as "content not allowed in prolog").
#### Notes
- `mcp-einvoicing-de` carries a pre-existing local copy of this exact class (`mcp_einvoicing_de/validators/schematron.py`), predating this core capability. Migrating DE to consume core's version instead is a separate, not-yet-done follow-up — see `gaps_registry.toml` id `core.schematron.xslt2_backend`.
- `mcp-facture-electronique-fr`'s `validate_facturx` tool (v0.6.0) still constructs its validator via `SchematronValidator` directly and needs to switch to `load_schematron_validator()` to pick up this fix — also a separate follow-up.

### [1.13.1] - 2026-06-30
#### Fixed
- `TaxIdentifier.validate_br_cnpj`: reject an all-equal-character base (root+branch, positions 0-11), mirroring the existing `validate_br_cpf` check (BR-TL-5). Closes the pathological gap where `"00000000000000"` passed the standard mod-11 checksum.

### [1.12.0] - 2026-06-29
#### Added
- `CAdESSigner` and `CAdESSignerConfig`: CMS/PKCS#7 attached signature (CAdES-BES) for IT FatturaPA .xml.p7m and FR Chorus Pro
- `BaseArchiveProvider` ABC and `ArchiveMetadata` model in new `mcp_einvoicing_core.archive` module
- Signer microservice: `algorithm` parameter on `sign` RPC method (xades / cades-bes)
- `SignerClient.sign()`: `algorithm` keyword argument for CAdES support

### [1.11.0] - 2026-06-28
#### Added
- Peppol BIS 3.0 schematron rules bundled under `specs/peppol/`: `CEN-EN16931-UBL-3.0.20.sch` and `PEPPOL-EN16931-UBL-3.0.20.sch` (from OpenPeppol tag v3.0.20)

### [1.10.0] - 2026-06-25
#### Added
- `mcp_einvoicing_core.peppol.transport` subpackage: Peppol AS4 outbound transmission primitives (CORE-AS4-1)
- `AS4MessageEnvelope`: ebMS3/AS4 SOAP envelope construction for invoice payloads
- `AS4TransportClient`: HTTP POST client with MIME multipart and X.509 message-level signing
- `AS4ReceiptHandler`: synchronous AS4 receipt signal message parser
- `PeppolTransmitter`: convenience wrapper combining SMP lookup, envelope, send, and receipt
- `AS4Receipt`, `AS4Credentials`: Pydantic models for receipt data and signing credentials
- Converted `peppol.py` to `peppol/` package (existing import paths unchanged)
- 10 unit tests for envelope structure, receipt parsing, and credential loading

### [1.9.0] - 2026-06-24
#### Added
- `TaxIdentifier.validate_fr_tva_intra()`: French TVA intracommunautaire number validator (FR-INV-2). Check key algorithm: `(12 + 3 * (SIREN mod 97)) mod 97`
- 8 new tests in `test_models.py`

### [1.8.0] - 2026-06-24
#### Added
- `BaseEnvironmentEndpoints`, `EndpointSet`, `EndpointEnvironment`: sandbox/production URL routing abstraction for country packages (CORE-URL-1)
- `EN16931CreditNote`, `BillingReference`: credit note model for type codes 381/383/384/385 with UBL and CII round-trip support (CORE-CN-1)
- `RoutingIdentifier.validate_de_leitweg`, `RoutingIdValidationResult`: Leitweg-ID format and ISO 7064 MOD 97-10 check digit validation promoted from DE (CORE-LWID-1)
- `convert_wire_format`, `Syntax`: CII/UBL wire format conversion composing the four EN16931 serializer/parser primitives (CORE-CONV-1)
- 26 new tests across 4 test files

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
