# mcp-einvoicing-core — Peppol specification assets

Reference files for the Peppol SMP/SML transport layer implemented in `peppol.py`.
All files sourced from the OpenPeppol AISBL publications portal (`https://docs.peppol.eu/edelivery/`).

## Normative XSD schemas

| File | Description | Version | Retrieved |
|---|---|---|---|
| `peppol-smp-types-v1.xsd` | SMP data model — `ServiceGroup`, `ServiceMetadata`, `SignedServiceMetadata`, `Endpoint`, `Redirect` | 1.0 | 2026-05-21 |
| `peppol-identifiers-v1.xsd` | Shared identifier types — `ParticipantIdentifier`, `DocumentIdentifier`, `ProcessIdentifier` | 1.0 | 2026-05-21 |
| `peppol-sml-types-v1.xsd` | SML data model — `ServiceMetadataPublisherService`, `CreateParticipantIdentifier`, `MigrationRecord` | 1.0 | 2026-05-21 |
| `PEPPOL-EDN-Business-Message-Envelope-1.2-2019-02-01.xsd` | BME v1.2 envelope schema — `BinaryContent`, `TextContent` (reference only; BME is out of scope for this library) | 1.2 | 2026-05-21 |

## Normative PDF specifications

| File | Description | Version | Retrieved |
|---|---|---|---|
| `Peppol-EDN-Service-Metadata-Publishing-1.4.0-2025-02-06.pdf` | SMP REST interface spec — data model, endpoint XML structure, HTTPS mandate, XML signature | 1.4.0 | 2026-05-21 |
| `Peppol-EDN-Service-Metadata-Locator-1.3.0-2025-02-06.pdf` | SML spec — DNS U-NAPTR discovery flow, `Meta:SMP` service name, management interfaces | 1.3.0 | 2026-05-21 |
| `Peppol-EDN-Policy-for-use-of-identifiers-4.4.0-2025-02-06.pdf` | Identifier policy — POLICY 7 DNS hash algorithm (Base32-SHA256), participant ID format, document type and process ID schemes | 4.4.0 | 2026-05-21 |
| `Peppol-EDN-Business-Message-Envelope-2.0.1-2023-08-17.pdf` | BME 2.0.1 spec — AS4 envelope structure (reference only; BME is out of scope for this library) | 2.0.1 | 2026-05-21 |
| `PEPPOL-EDN-Directory-1.1.1-2020-10-15.pdf` | Peppol Directory spec — REST search API, business-card data model, PD-SML connection. Implemented as `peppol.directory.PeppolDirectoryClient` (CORE-PEPPOL-DIR-1, shipped v1.20.0) | 1.1.1 | 2026-08-21 |
| `PEPPOL-EDN-Policy-for-Transport-Security-1.1.0-2020-04-20.pdf` | TLS/certificate policy for SMP, Directory, and AP actors. Note: covers **TLS** certs only (public-CA-issued, non-self-signed) — it does not publish the separate OpenPeppol application-level PKI root/intermediate certs `peppol.trust` needs; those are the still-pending vendoring item (see `pki/` below) | 1.1.0 | 2026-08-21 |
| `Peppol-AS4-Profile-2.0.3.pdf` | AS4 Profile — Peppol-specific restrictions on top of [CEFeDeliveryAS4] v1.14 (not vendored): One-Way/Push only, Peppol PKI BST-based signing (§4.7), mandatory SBDH (§4.9), `PEPPOL:NOT_SERVICED` error (§4.4). Implemented as `peppol.transport.wssecurity`/`.inbound` (AS4-SIGN-1/AS4-IN-1, shipped v1.20.0). The exact WS-Security wire format (canonicalization, Reference/Transform shapes) is not in this doc — it defers to [CEFeDeliveryAS4] §3.2.6, not vendored; the implementation follows the stable OASIS WS-Security/SwA-Profile standards directly, flagged `[NEED: verify]` in `wssecurity.py`'s module docstring pending that doc | 2.0.3 | 2026-08-22 |
| `Peppol-EDN-Business-Message-Envelope-2.0.2-2026-07-02.pdf` | SBDH envelope v2.0.2 — newer than the 2.0.1 PDF and 1.2 XSD already vendored below; bonus artifact from the AS4 supply pass, not yet consumed (2.0.1/1.2 remain the versions the current SBDH parsing in `peppol.transport.inbound`/`models.StandardBusinessDocumentHeader` was verified against, via the MLS example snippets) | 2.0.2 | 2026-08-22 |

**Licensing note (2026-08-21):** every PDF in this table carries an in-file "Statement of copyright"
granting **Creative Commons BY-NC-ND 4.0** (checked directly across all seven: the three vendored
2026-05-21 and the two added here, all identical boilerplate) — "Share: copy and redistribute the
material in any medium or format," permissive for verbatim redistribution, but NonCommercial and
NoDerivatives. `mcp-einvoicing-core` is Apache-2.0, open source, and not operated for commercial
purposes (confirmed with the project owner 2026-08-21) — this satisfies NC, and these files are
vendored unmodified — this satisfies ND. This is a broader, cleaner grant than the CEN/Peppol
Schematron overlay's total absence of a redistribution license (see the schematron licensing note
below); the two should not be conflated.

## Peppol BIS Billing 3.0 schematron rules

| File | Description | Version | Retrieved |
|---|---|---|---|
| `PEPPOL-EN16931-UBL-3.0.20.sch` | Peppol BIS Billing 3.0 UBL validation rules (Peppol-layer business rules on top of CEN EN 16931) | 3.0.20 | 2026-06-27 |
| `CEN-EN16931-UBL-3.0.20.sch` | CEN EN 16931 UBL validation rules (core business rules) | 3.0.20 | 2026-06-27 |
| `stylesheet-ubl.xslt` | XSLT stylesheet for rendering UBL 2.1 invoices to human-readable HTML | 3.0.20 | 2026-06-28 |
| `BIS-Billing3-Examples.zip` | Official OpenPeppol BIS Billing 3.0 example UBL invoices (golden XML test vectors) | 3.0.20 | 2026-06-28 |

Source: `https://docs.peppol.eu/poacc/billing/3.0/` and `https://github.com/OpenPeppol/peppol-bis-invoice-3/tree/v3.0.20/rules/sch`

The BIS Billing 3.0 specification itself is published as a web document at `https://docs.peppol.eu/poacc/billing/3.0/bis/` (no standalone PDF available).

**Licensing note (2026-08-19):** `CEN-EN16931-UBL-3.0.20.sch` carries an explicit, in-file
`Licensed under European Union Public Licence (EUPL) version 1.2.` grant. `PEPPOL-EN16931-UBL-
3.0.20.sch` and `stylesheet-ubl.xslt` do not — their headers only say content is "reproduced with
permission from CEN" without stating redistribution terms, and the source repo
(`OpenPEPPOL/peppol-bis-invoice-3`) carries no root `LICENSE`/`NOTICE` file. Confirmed against
`docs.peppol.eu/poacc/billing/3.0/bis/`'s current copyright statement, which requires OpenPeppol
AISBL's prior consent for any redistribution or modification. Full investigation and decision in
[`context-library/decisions/peppol-schematron-artifact.md`](../../../context-library/decisions/peppol-schematron-artifact.md)
(root repo). **Practical effect:** only `CEN-EN16931-UBL-3.0.20.sch` may be compiled and shipped in
a package wheel; `PEPPOL-EN16931-UBL-3.0.20.sch` and `stylesheet-ubl.xslt` stay here as
compile-input/verification references only, never as build output.

## Build tooling

| Tool | Version | Source | License | Retrieved | Used for |
|---|---|---|---|---|---|
| SchXslt2 | 1.11.2 | `https://codeberg.org/SchXslt/schxslt2/releases/download/v1.11.2/schxslt2-1.11.2.zip` | MIT (David Maus) | 2026-08-20 | Compiling `CEN-EN16931-UBL-3.0.20.sch` into a validating XSLT 3.0 stylesheet (`transpile.xsl`), run via `saxonche` (the `[xslt2]` extra core already depends on) — see `scripts/compile_en16931_base_schematron.py`. Not a runtime dependency; dev/CI-time only. |

Vendored copy (with its own `LICENSE`) lives at `mcp-einvoicing-core/scripts/vendor/schxslt2-1.11.2/`,
outside `specs/` since it is build tooling, not a normative spec. SchXslt2 is the maintained
successor to the original SchXslt (`codeberg.org/SchXslt/schxslt`, now maintenance-mode-only); it
targets XSLT 3.0, a strict superset of the XPath 2.0 our `.sch` files declare
(`queryBinding="xslt2"`), so it compiles them without modification. Only used against
`CEN-EN16931-UBL-3.0.20.sch` per the licensing note above — never against the Peppol overlay file.

## Peppol Directory business-card schema

| File | Description | Version | Retrieved |
|---|---|---|---|
| `directory/peppol-directory-business-card-20180621.xsd` | Peppol Directory business-card XML schema (Apache-2.0, Philip Helger). §5.2.2/§8 of the vendored Directory spec confirm this shape underlies the search response's per-match entity data, resolving the earlier `[NEED]` — no longer speculative. Kept as a local reference only (not bundled in the wheel): `peppol.directory` parses the Directory's JSON search output directly, not this XML shape | 20180621 | 2026-08-22 |

## OpenPeppol eDEC network code lists (deployer-supplied — not bundled)

`codelists/*.gc` (Document types, Participant identifier schemes, Processes, Transport profiles,
SPIS use case, all v9.7) are OASIS Genericode 1.0 reference copies used only to develop/test
`peppol.codelists` locally — **not shipped in the published wheel**. The eDEC Code Lists carry no
in-file redistribution grant (see `core-state.md`'s "Peppol eDEC code lists" section for the full
licensing investigation); every real deployment supplies its own copy via
`EINVOICING_PEPPOL_CODELIST_DIR`. The parser (`mcp_einvoicing_core.genericode.parse_genericode`,
extracted from `peppol.codelists` in v1.20.0) is shared with the EN 16931 semantic code lists at
`../en16931/codelists/` — see `../en16931/README.md`.

## Peppol reporting (EUSR/TSR) and MLS artifacts — v1.20.0, Apache-2.0, bundled

| Directory | Description | License confirmed |
|---|---|---|
| `reporting/eusr/{xsd,schematron,codelist,example}/` | End User Statistics Report v1.1: XSD, compiled Schematron `.xslt` (XSLT 2.0), genericode code lists, official example XMLs | Apache-2.0, 2026-08-22 |
| `reporting/tsr/{xsd,schematron,codelist,example}/` | Transaction Statistics Report v1.0: same shape as EUSR | Apache-2.0, 2026-08-22 |
| `mls/{schematron,codelist,example}/` | Message Level Status v1.1.0: compiled Schematron `.xslt` (XSLT 2.0, no bespoke MLS XSD — message syntax is a UBL `ApplicationResponse-2` subset), genericode code lists, official example XMLs (incl. SBDH snippets) | Apache-2.0, 2026-08-22 |

Unlike the CC BY-NC-ND PDFs and the unlicensed Peppol Schematron overlay above, these three
artifact sets carry a genuine Apache-2.0 grant (confirmed by the user 2026-08-22) and are
therefore compiled/copied into the published wheel: XSD + compiled `.xslt` + `.gc` under
`mcp-einvoicing-core/src/mcp_einvoicing_core/resources/{reporting/eusr,reporting/tsr,mls}/`. The
`.sch` source, PDFs, and `example/` fixtures stay here (spec reference / test fixtures only, not
shipped). Implemented as `peppol.reporting` (CORE-PEPPOL-REPORT-1) and `peppol.mls`
(CORE-PEPPOL-MLR-1).

## Peppol PKI trust anchors (`pki/`) — placeholder, not yet supplied

`pki/test/` and `pki/prod/` are empty placeholders for the OpenPeppol application-level PKI
root/intermediate CA certificates (distinct from the TLS policy above — see the
Transport-Security PDF row's note). `peppol.trust.PeppolTrustStore` reads
`EINVOICING_PEPPOL_PKI_DIR/{test,prod}/*.{pem,crt,cer}` and reports
`trust_anchors_configured: False` until these are populated; chain validation and revocation
checking logic is implemented and tested (CORE-PEPPOL-TRUST-1, v1.20.0), just unable to run for
real until the certs land here.

## Key namespaces

| Prefix | Namespace URI | Used in |
|---|---|---|
| `smp` | `http://busdox.org/serviceMetadata/publishing/1.0/` | `ServiceGroup`, `ServiceMetadata`, `SignedServiceMetadata` |
| `ids` | `http://busdox.org/transport/identifiers/1.0/` | `ParticipantIdentifier`, `DocumentIdentifier`, `ProcessIdentifier` |
| `wsa` | `http://www.w3.org/2005/08/addressing` | `EndpointReference/Address` (the AS4 endpoint URL) |
| `lrs` | `http://busdox.org/serviceMetadata/locator/1.0/` | SML management types |

## Breaking changes identified in 2025 specs

These changes affect `peppol.py` and are tracked in `context-library/roadmap-2026.md` as
`CORE-PEPPOL-1` through `CORE-PEPPOL-7`.

| Spec | Change | Impact |
|---|---|---|
| Policy for use of Identifiers 4.4.0, POLICY 7 | DNS hash: Base32-encoded SHA-256 of lowercased `<scheme>:<value>` only (was hex SHA-256 of full `iso6523-actorid-upis::<scheme>:<value>`); `B-` prefix removed; numeric scheme replaced by `iso6523-actorid-upis` in DNS name | `dns_hash()`, `dns_name()` |
| SML 1.3.0 | DNS record type changed from CNAME (type 5) to U-NAPTR (type 35); service name `Meta:SMP`; SMP base URL extracted from NAPTR URI field | `_resolve_smp_hostname()` |
| SMP 1.4.0 | Endpoint URL is `wsa:EndpointReference/wsa:Address`, not an `EndpointURI` element | `_parse_service_metadata()` |
| SMP 1.4.0 / XSD | `transportProfile` is an XML attribute on `<Endpoint>`, not a child element | `_parse_service_metadata()` |
| SMP 1.4.0 | `ServiceMetadata` may contain `<Redirect>` instead of `<ServiceInformation>` | `_parse_service_metadata()` |

## Excluded files (not copied)

| File | Reason excluded |
|---|---|
| `peppol-sml-manage-*.wsdl` (both) | SML management SOAP interfaces — for SMP operators registering participants, not for invoice compliance clients. Re-checked 2026-08-21 against `[CORE-PEPPOL-SML-1]`: license is clean (MIT-style OpenPeppol AISBL grant) but the scope reasoning still holds — stays excluded |
| `2024-01-15 Peppol Reporting - SP Operational Guideline v1.0.2.pdf` | SP operational reporting — separate concern |
| `OpenPeppol-SP-ID-Scheme 1.0.0.pdf` | SP identification scheme — not relevant to SMP client |

## Update process

When OpenPeppol publishes a new version of any included spec:

1. Download the new file from `https://docs.peppol.eu/edelivery/`.
2. Replace the file here and update the version and retrieved date in the table above.
3. Review the revision history section of the new spec for breaking changes.
4. Update `context-library/roadmap-2026.md` with any new `CORE-PEPPOL-*` items.
5. Update the breaking changes table above.
