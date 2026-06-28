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

## Peppol BIS Billing 3.0 schematron rules

| File | Description | Version | Retrieved |
|---|---|---|---|
| `PEPPOL-EN16931-UBL-3.0.20.sch` | Peppol BIS Billing 3.0 UBL validation rules (Peppol-layer business rules on top of CEN EN 16931) | 3.0.20 | 2026-06-27 |
| `CEN-EN16931-UBL-3.0.20.sch` | CEN EN 16931 UBL validation rules (core business rules) | 3.0.20 | 2026-06-27 |

| `stylesheet-ubl.xslt` | XSLT stylesheet for rendering UBL 2.1 invoices to human-readable HTML | 3.0.20 | 2026-06-28 |
| `BIS-Billing3-Examples.zip` | Official OpenPeppol BIS Billing 3.0 example UBL invoices (golden XML test vectors) | 3.0.20 | 2026-06-28 |

Source: `https://docs.peppol.eu/poacc/billing/3.0/` and `https://github.com/OpenPeppol/peppol-bis-invoice-3/tree/v3.0.20/rules/sch`

The BIS Billing 3.0 specification itself is published as a web document at `https://docs.peppol.eu/poacc/billing/3.0/bis/` (no standalone PDF available).

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
| `peppol-sml-manage-*.wsdl` (both) | SML management SOAP interfaces — for SMP operators registering participants, not for invoice compliance clients |
| `peppol-directory-business-card-20180621.xsd` | Peppol Directory business card — participant search UI, out of scope |
| `PEPPOL-EDN-Directory-1.1.1-2020-10-15.pdf` | Peppol Directory spec — out of scope |
| `PEPPOL-EDN-Policy-for-Transport-Security-1.1.0-2020-04-20.pdf` | AS4 mTLS policy — for access point operators, not SMP lookup clients |
| `2024-01-15 Peppol Reporting - SP Operational Guideline v1.0.2.pdf` | SP operational reporting — separate concern |
| `OpenPeppol-SP-ID-Scheme 1.0.0.pdf` | SP identification scheme — not relevant to SMP client |

## Update process

When OpenPeppol publishes a new version of any included spec:

1. Download the new file from `https://docs.peppol.eu/edelivery/`.
2. Replace the file here and update the version and retrieved date in the table above.
3. Review the revision history section of the new spec for breaking changes.
4. Update `context-library/roadmap-2026.md` with any new `CORE-PEPPOL-*` items.
5. Update the breaking changes table above.
