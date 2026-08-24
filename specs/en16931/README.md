# mcp-einvoicing-core — EN 16931 semantic code-list assets

Reference files for the EN 16931 semantic code-list lookup implemented in
`mcp_einvoicing_core.en16931_codelists` (CORE-EN16931-CODELIST-1, shipped v1.20.0). All files
sourced from the CEF "Digital Building Blocks for Europe" code list distribution.

## Code lists (deployer-supplied — not bundled)

| File | Description | Version | Retrieved |
|---|---|---|---|
| `codelists/Country.gc` | ISO 3166-1 alpha-2 country codes | 2026-05-15 | 2026-08-22 |
| `codelists/Currency.gc` | ISO 4217 currency codes | 2026-05-15 | 2026-08-22 |
| `codelists/ICD.gc` | ISO 6523 ICD (International Code Designator) | 2026-05-15 | 2026-08-22 |
| `codelists/1001.gc` | UNCL1001 document name codes | 2026-05-15 | 2026-08-22 |
| `codelists/1153.gc` | UNCL1153 reference qualifier codes | 2026-05-15 | 2026-08-22 |
| `codelists/Payment.gc` | UNCL4461 payment means codes | 2026-05-15 | 2026-08-22 |
| `codelists/5305.gc` | UNCL5305 VAT category codes | 2026-05-15 | 2026-08-22 |
| `codelists/Allowance.gc` | Allowance reason codes | 2026-05-15 | 2026-08-22 |
| `codelists/Item.gc` | Item type identification codes | 2026-05-15 | 2026-08-22 |
| `codelists/Charge.gc` | Charge reason codes | 2026-05-15 | 2026-08-22 |
| `codelists/MIME.gc` | Recognized MIME types for embedded attachments | 2026-05-15 | 2026-08-22 |
| `codelists/EAS.gc` | Electronic Address Scheme (EAS) codes | 2026-05-15 | 2026-08-22 |
| `codelists/VATEX.gc` | VATEX VAT exemption reason codes | 2026-05-15 | 2026-08-22 |
| `codelists/Text.gc`, `codelists/Unit.gc` | Bonus files from the same CEF zip (UN/ECE Recommendation 20 unit codes and a text codelist); not consumed by `en16931_codelists` today — kept for reference, not a gap | 2026-05-15 | 2026-08-22 |
| `codelists/*.xlsx` (Electronic Address Scheme, VAT Exemption Reason Code list) | Optional human-readable backups of the EAS/VATEX `.gc` files, supplied alongside the zip | v16 / v8 | 2026-08-22 |

Source: the "as Genericode" export bundle from the CEF EN 16931 code lists page (supplied locally
by the user as `digital-genericodes-2026-05-15.zip`, not fetched by Claude).

**Licensing: same posture as the Peppol eDEC code lists** (see
`../peppol/README.md` and `core-state.md`'s "Peppol eDEC code lists" section for the full
investigation this mirrors). The `.gc` files carry only an "automatically generated, do not edit"
annotation — no copyright or redistribution grant. **Data is NOT bundled** in the published wheel;
each deployment supplies its own local copy and points `EINVOICING_EN16931_CODELIST_DIR` at the
directory containing it. Every `list_*`/`check_*` tool returns `configured: false` with guidance
when unset, rather than raising past the tool boundary (raises `CodelistNotConfiguredError` at the
module level, matching `peppol.codelists`'s pattern).

**Filename matching differs from the eDEC lists:** no glob/version prefix matching — `.gc`
basenames match the CEF zip's own filenames exactly (`Country.gc`, not `Country-v1.gc`). A CEF
version bump changes only each file's internal `<Version>` element, not its filename, so
`get_en16931_codelist_version()` is the only place a version change surfaces.

Verified 2026-08-22/23 against the 2026-05-15 CEF release: all 13 consumed lists parse via the
shared `mcp_einvoicing_core.genericode.parse_genericode` (extracted out of `peppol.codelists` in
v1.20.0 specifically so this module could reuse it) and every `check_*` tool returns correct
results against real entries (e.g. `EUR`, `VATEX-EU-79-C`).

## Update process

When the CEF publishes a new version of the code list bundle:

1. Download the new "as Genericode" export from the CEF EN 16931 code lists page.
2. Replace the `.gc` files here (same basenames — no renaming).
3. Update the version and retrieved date in the table above.
4. No code changes are needed — `en16931_codelists.py` matches by exact basename, not version.
