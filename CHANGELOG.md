# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [1.25.0] - 2026-08-29

### Added
- `en16931.py`: `EN16931Invoice.document_uuid` — optional field emitted as
  `<cbc:UUID>`, a sibling immediately after `<cbc:ID>` in UBL 2.1 output.
  Several Peppol jurisdiction CIUS profiles mandate a document UUID (e.g.
  PINT AE BTAE-07, PINT-SG BT-SG-003); previously each country package had
  no core hook to emit it. `None` by default, so existing packages that
  never set it produce byte-identical output to before this change.
- `wire_formats.py`: `EN16931UBLSerializer._emit_item_price_extension`
  (default `False`) — an opt-in flag for country subclasses that must emit
  `cac:ItemPriceExtension` per invoice line (line net amount + line VAT
  amount, and the line VAT amount, as a sibling of `cac:Price`). Not part of
  base EN 16931 or generic Peppol BIS 3.0 — confirmed absent from the BE,
  DE, IT, PL, ES, SG, FR specs vendored in this workspace; present only in
  PINT AE's jurisdiction rules (ibr-104-ae/ibr-194-ae). Base behavior is
  unchanged for every package that doesn't opt in.

### Fixed
- `audit.py`: `_read_core_version_spec` (CHECK 4) no longer matches a prose
  comment line that happens to contain the substring `"mcp-einvoicing-core"`
  when it precedes the real dependency-array entry — it now only matches
  lines that are themselves a TOML string literal starting with the package
  name. Both `mcp-invoicenow-sg` and `mcp-einvoicing-ae` carry an explanatory
  comment directly above their dependency line and were hitting this bug,
  rendering a garbled "declared range" in their audit reports.

---

## [1.23.0] - 2026-08-27

### Added
- `ubl_documents.py`: new `BaseUBLDocument` model — a shared envelope
  (`document_id`, `issue_date`, `customization_id`, `profile_id`, `sender`/
  `receiver` as `PeppolParticipantId`) for non-invoice UBL/Peppol document
  families (Peppol Ordering: Order, OrderResponse, OrderChange,
  OrderCancellation, OrderAgreement, Invoice Response, and jurisdiction
  extensions such as Singapore IMDA's Order Balance). Explicitly outside the
  canonical invoice tree (`InvoiceDocument`/`EN16931Invoice`) per CLAUDE.md —
  never subclass one for the other. Resolves the `mcp-invoicenow-sg`
  (Singapore) roadmap item SG-INV-2. Additive, non-breaking.

---

## [1.20.1] - 2026-08-25

### Changed
- `en16931.py`: verified the full EN 16931 semantic model (BT-1 through
  BT-161, BG-1 through BG-32) against NF EN 16931-1:2017+A1:2019 (AFNOR),
  Article 6.3, Tableau 2. No mislabeled BT number was found. Lifted the
  `[Inference]` disclaimer on the module docstring to
  `[Verified against NF EN 16931-1:2017+A1:2019 §6.3]` and added an explicit
  coverage statement of the optional BTs/BGs this module deliberately omits.

### Added
- `tests/test_en16931_bt_mapping.py`: regression test pinning each
  `en16931.py` field's declared BT reference, so an edit to a
  `Field(description=...)` string cannot silently drift the field -> BT
  mapping.

---

## [1.19.0] - 2026-08-22

### Added
- Initial changelog. Prior release history is recorded in the Git tags and
  GitHub Releases for this repository.
