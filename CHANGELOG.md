# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
