# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
