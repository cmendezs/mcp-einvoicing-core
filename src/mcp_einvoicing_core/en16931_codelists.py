"""EN 16931 semantic code-list lookup: country, currency, ICD, UNCL document
name / reference qualifier / payment means / VAT category / allowance /
item type / charge reason codes, MIME types, EAS, VATEX.

Like ``mcp_einvoicing_core.peppol.codelists`` (the identical situation for
the OpenPeppol eDEC code lists), this module does NOT bundle the underlying
data inside the wheel. The CEF "Digital Building Blocks for Europe" code
lists carry no in-file redistribution grant, so each deployment supplies its
own local copy: download the "as Genericode" export bundle from
https://ec.europa.eu/digital-building-blocks/sites/display/DIGITAL/EN16931+code+lists
and point EINVOICING_EN16931_CODELIST_DIR at the directory containing the
``.gc`` files. Filenames are matched exactly against the basenames the CEF
zip ships (e.g. "Country.gc", "5305.gc"), no glob/version matching — a
version bump only changes each file's internal ``<Version>`` element, not
its filename, so `get_en16931_codelist_version()` is the only place a
version change surfaces.

Verified 2026-08-22 against the 2026-05-15 CEF release
(``digital-genericodes-2026-05-15.zip``).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from mcp_einvoicing_core.genericode import CodeList, CodelistNotConfiguredError, parse_genericode

logger = logging.getLogger(__name__)

_ENV_VAR = "EINVOICING_EN16931_CODELIST_DIR"

# Codelist name -> exact .gc basename, matching the CEF zip's own filenames.
_CODELIST_BASENAMES: dict[str, str] = {
    "country": "Country",
    "currency": "Currency",
    "icd": "ICD",
    "document_name_code": "1001",  # UNCL1001
    "reference_qualifier": "1153",  # UNCL1153
    "payment_means_code": "Payment",  # UNCL4461
    "vat_category_code": "5305",  # UNCL5305
    "allowance_reason_code": "Allowance",
    "item_type_code": "Item",
    "charge_reason_code": "Charge",
    "mime_code": "MIME",
    "eas": "EAS",
    "vatex": "VATEX",
}


def _codelist_dir() -> Path:
    raw = os.environ.get(_ENV_VAR, "").strip()
    if not raw:
        raise CodelistNotConfiguredError(
            f"{_ENV_VAR} is not set. EN 16931 code-list tools require a local "
            "copy of the CEF 'Digital Building Blocks for Europe' code lists "
            "(not bundled with this package, no confirmed redistribution "
            "rights, same posture as the Peppol eDEC code lists — see "
            "mcp_einvoicing_core.peppol.codelists). Download the 'as "
            "Genericode' export bundle and set "
            f"{_ENV_VAR} to the directory containing the .gc files."
        )
    directory = Path(raw)
    if not directory.is_dir():
        raise CodelistNotConfiguredError(f"{_ENV_VAR}={raw!r} is not a directory.")
    return directory


def _find_codelist_file(directory: Path, basename: str) -> Path:
    path = directory / f"{basename}.gc"
    if not path.is_file():
        raise CodelistNotConfiguredError(
            f"No file {basename}.gc found under {directory}. Download the "
            "'as Genericode' export bundle from the CEF EN 16931 code lists "
            "page."
        )
    return path


def load_codelist(name: str) -> CodeList:
    """Load and parse a named EN 16931 code list from EINVOICING_EN16931_CODELIST_DIR.

    Args:
        name: One of "country", "currency", "icd", "document_name_code",
            "reference_qualifier", "payment_means_code", "vat_category_code",
            "allowance_reason_code", "item_type_code", "charge_reason_code",
            "mime_code", "eas", "vatex".

    Raises:
        KeyError: If *name* is not a recognized codelist name.
        CodelistNotConfiguredError: If the env var is unset, the directory
            does not exist, or the matching file is not found under it.
    """
    basename = _CODELIST_BASENAMES[name]
    directory = _codelist_dir()
    path = _find_codelist_file(directory, basename)
    return parse_genericode(path.read_bytes())


def _list(name: str) -> list[dict[str, str | None]]:
    return load_codelist(name).rows


def _check(name: str, code: str) -> dict[str, object]:
    for row in load_codelist(name).rows:
        if row.get("Code") == code:
            return {"found": True, **row}
    return {"found": False, "Code": code}


def list_country_codes() -> list[dict[str, str | None]]:
    """Return ISO 3166-1 alpha-2 country code rows (Code, Name)."""
    return _list("country")


def check_country_code(code: str) -> dict[str, object]:
    """Check whether *code* is a recognized ISO 3166-1 alpha-2 country code."""
    return _check("country", code)


def list_currency_codes() -> list[dict[str, str | None]]:
    """Return ISO 4217 currency code rows (Code, Name)."""
    return _list("currency")


def check_currency_code(code: str) -> dict[str, object]:
    """Check whether *code* is a recognized ISO 4217 currency code."""
    return _check("currency", code)


def list_icd_codes() -> list[dict[str, str | None]]:
    """Return ISO 6523 ICD (International Code Designator) rows (Code, Name)."""
    return _list("icd")


def check_icd_code(code: str) -> dict[str, object]:
    """Check whether *code* is a recognized ISO 6523 ICD code."""
    return _check("icd", code)


def list_document_name_codes() -> list[dict[str, str | None]]:
    """Return UNCL1001 document name code rows (Code, Name, Remark)."""
    return _list("document_name_code")


def check_document_name_code(code: str) -> dict[str, object]:
    """Check whether *code* is a recognized UNCL1001 document name code."""
    return _check("document_name_code", code)


def list_reference_qualifier_codes() -> list[dict[str, str | None]]:
    """Return UNCL1153 reference qualifier code rows (Code, Name)."""
    return _list("reference_qualifier")


def check_reference_qualifier_code(code: str) -> dict[str, object]:
    """Check whether *code* is a recognized UNCL1153 reference qualifier code."""
    return _check("reference_qualifier", code)


def list_payment_means_codes() -> list[dict[str, str | None]]:
    """Return UNCL4461 payment means code rows (Code, Name, Remark)."""
    return _list("payment_means_code")


def check_payment_means_code(code: str) -> dict[str, object]:
    """Check whether *code* is a recognized UNCL4461 payment means code."""
    return _check("payment_means_code", code)


def list_vat_category_codes() -> list[dict[str, str | None]]:
    """Return UNCL5305 VAT category code rows (Code, Name, Remark)."""
    return _list("vat_category_code")


def check_vat_category_code(code: str) -> dict[str, object]:
    """Check whether *code* is a recognized UNCL5305 VAT category code."""
    return _check("vat_category_code", code)


def list_allowance_reason_codes() -> list[dict[str, str | None]]:
    """Return allowance reason code rows (Code, Name)."""
    return _list("allowance_reason_code")


def check_allowance_reason_code(code: str) -> dict[str, object]:
    """Check whether *code* is a recognized allowance reason code."""
    return _check("allowance_reason_code", code)


def list_item_type_codes() -> list[dict[str, str | None]]:
    """Return item type identification code rows (Code, Name)."""
    return _list("item_type_code")


def check_item_type_code(code: str) -> dict[str, object]:
    """Check whether *code* is a recognized item type identification code."""
    return _check("item_type_code", code)


def list_charge_reason_codes() -> list[dict[str, str | None]]:
    """Return charge reason code rows (Code, Name)."""
    return _list("charge_reason_code")


def check_charge_reason_code(code: str) -> dict[str, object]:
    """Check whether *code* is a recognized charge reason code."""
    return _check("charge_reason_code", code)


def list_mime_codes() -> list[dict[str, str | None]]:
    """Return recognized MIME type rows (Code only)."""
    return _list("mime_code")


def check_mime_code(code: str) -> dict[str, object]:
    """Check whether *code* is a recognized MIME type for embedded attachments."""
    return _check("mime_code", code)


def list_eas_codes() -> list[dict[str, str | None]]:
    """Return Electronic Address Scheme (EAS) code rows (Code, Name)."""
    return _list("eas")


def check_eas_code(code: str) -> dict[str, object]:
    """Check whether *code* is a recognized Electronic Address Scheme code."""
    return _check("eas", code)


def list_vatex_codes() -> list[dict[str, str | None]]:
    """Return VATEX (VAT exemption reason) code rows (Code, Name, Remark)."""
    return _list("vatex")


def check_vatex_code(code: str) -> dict[str, object]:
    """Check whether *code* is a recognized VATEX VAT exemption reason code."""
    return _check("vatex", code)


def get_en16931_codelist_version() -> dict[str, object]:
    """Report the EN 16931 code-list release version(s) currently configured locally.

    Returns a dict with "versions" (codelist name -> version string, for
    each list that loaded successfully) and "errors" (codelist name -> error
    message, for each list that is missing or unreadable).
    """
    versions: dict[str, str] = {}
    errors: dict[str, str] = {}
    for name in _CODELIST_BASENAMES:
        try:
            versions[name] = load_codelist(name).version
        except CodelistNotConfiguredError as exc:
            errors[name] = str(exc)
    return {"versions": versions, "errors": errors}
