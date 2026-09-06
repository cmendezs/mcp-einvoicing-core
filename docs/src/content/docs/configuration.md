---
title: Configuration
description: Environment variables for mcp-einvoicing-core.
---

| Variable | Used by | Purpose |
|---|---|---|
| `EINVOICING_PEPPOL_CODELIST_DIR` | `peppol.codelists` (and the `peppol.tools` codelist tools) | Local directory containing your own copy of the OpenPeppol eDEC Code Lists. **Not bundled with this package**: the eDEC Code Lists carry no confirmed redistribution grant from OpenPeppol, so core ships only the parser and lookup tools, never the data itself. Download the "as GeneriCode" export for each artifact (Document Types, Participant Identifier Schemes, Processes, Transport Profiles, SPIS Use Case) from [docs.peppol.eu/edelivery/codelists](https://docs.peppol.eu/edelivery/codelists/index.html) and point this variable at the directory containing them. Filenames are matched by prefix, so a version bump (e.g. v9.7 to v9.8) needs no code change. Without this set, the codelist tools return a `configured: false` result with setup instructions rather than raising. |
| `EINVOICING_EN16931_CODELIST_DIR` | `en16931_codelists` (and its FastMCP tools) | Local directory containing your own copy of the CEF EN 16931 semantic code lists (country, currency, ICD, UNCL1001/1153/4461/5305, allowance/item/charge reason, MIME, EAS, VATEX). **Not bundled**, same posture as the eDEC lists above — download the "as GeneriCode" export bundle from the CEF EN 16931 code lists page. Filenames match exactly (`Country.gc`, not a version-prefixed name). Without this set, tools return `configured: false`. |
| `EINVOICING_PEPPOL_PKI_DIR` | `peppol.trust` | Local directory with `test/` and `prod/` subdirectories of PEM-encoded OpenPeppol PKI root/intermediate CA certificates, for AS4 message signature and SMP response signature chain validation. Not yet published by OpenPeppol as bundled data anywhere — trust functions report `trust_anchors_configured: false` until this is set. |
| `EINVOICING_SMP_ALLOWLIST` | `peppol` (`PeppolSMPClient`, `resolve_naptr`) | Comma-separated hostname suffixes to extend the built-in Peppol Access Point allowlist used when validating a resolved SMP hostname. |
