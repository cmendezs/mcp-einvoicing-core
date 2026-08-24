"""Peppol service-provider statistics reports: EUSR and TSR (CORE-PEPPOL-REPORT-1).

Models and XSD + Schematron validation for the two service-provider-only
Peppol reports:

- **EUSR** — End User Statistics Report (``urn:fdc:peppol:end-user-statistics-report:1.1``),
  per the vendored "Peppol End User Statistics Reporting Process" spec.
- **TSR** — Transaction Statistics Report (``urn:fdc:peppol:transaction-statistics-report:1.0``),
  per the vendored "Peppol Transaction Statistics Reporting Process" spec.

Both are standalone report documents (not invoices) — they subclass neither
`EN16931Invoice` nor `InvoiceDocument`. Structure confirmed against the
vendored XSDs and the ``example/*.xml`` fixtures shipped alongside them
(``specs/peppol/reporting/{eusr,tsr}/``); Apache-2.0 confirmed 2026-08-22
(see ``specs/peppol/README.md``), so the XSD, compiled Schematron ``.xslt``,
and genericode code lists are bundled inside the wheel under
``resources/reporting/{eusr,tsr}/``.

Schematron validation requires the ``[xslt2]`` optional extra (``saxonche``)
— both stylesheets declare ``version="2.0"`` — the same requirement as
`mcp_einvoicing_core.schematron_artifacts.en16931_base_schematron_validator`.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from mcp_einvoicing_core.genericode import CodeList, parse_genericode
from mcp_einvoicing_core.schematron import (
    BaseStructuredValidator,
    ValidationResult,
    XSDValidator,
    load_schematron_validator,
)
from mcp_einvoicing_core.xml_utils import safe_fromstring

_RESOURCES_DIR = Path(__file__).parent.parent / "resources" / "reporting"

_EUSR_XSD = _RESOURCES_DIR / "eusr" / "xsd" / "peppol-end-user-statistics-reporting-1.1.xsd"
_EUSR_SCHEMATRON = (
    _RESOURCES_DIR / "eusr" / "schematron" / "peppol-end-user-statistics-reporting-1.1.4.xslt"
)
_EUSR_CODELIST_DIR = _RESOURCES_DIR / "eusr" / "codelist"

_TSR_XSD = _RESOURCES_DIR / "tsr" / "xsd" / "peppol-transaction-statistics-reporting-1.0.xsd"
_TSR_SCHEMATRON = (
    _RESOURCES_DIR / "tsr" / "schematron" / "peppol-transaction-statistics-reporting-1.0.4.xslt"
)
_TSR_CODELIST_DIR = _RESOURCES_DIR / "tsr" / "codelist"

_EUSR_NS = "urn:fdc:peppol:end-user-statistics-report:1.1"
_TSR_NS = "urn:fdc:peppol:transaction-statistics-report:1.0"


# ---------------------------------------------------------------------------
# Shared models
# ---------------------------------------------------------------------------


class ReportPeriod(BaseModel):
    """``<Header><ReportPeriod>``: the calendar period a report covers."""

    start_date: str
    end_date: str


class ReporterID(BaseModel):
    """``<Header><ReporterID schemeID="...">...</ReporterID>``."""

    scheme_id: str
    value: str


class ReportHeader(BaseModel):
    """Shared ``<Header>`` structure of both EUSR and TSR."""

    report_period: ReportPeriod
    reporter_id: ReporterID


class ReportKey(BaseModel):
    """A single ``<Key metaSchemeID="..." schemeID="...">...</Key>`` dimension
    on a Subset (EUSR) or Subtotal (TSR)."""

    meta_scheme_id: str
    scheme_id: str
    value: str


# ---------------------------------------------------------------------------
# EUSR — End User Statistics Report
# ---------------------------------------------------------------------------


class EUSRFullSet(BaseModel):
    """``<FullSet>``: the report-wide end-user counts (always present)."""

    sending_end_users: int
    receiving_end_users: int
    sending_or_receiving_end_users: int


class EUSRSubset(BaseModel):
    """A single ``<Subset type="...">`` breakdown (0..n per report)."""

    type: str
    keys: list[ReportKey] = Field(default_factory=list)
    sending_end_users: int
    receiving_end_users: int
    sending_or_receiving_end_users: int


class EndUserStatisticsReport(BaseModel):
    """A parsed EUSR document (``urn:fdc:peppol:end-user-statistics-report:1.1``)."""

    customization_id: str
    profile_id: str
    header: ReportHeader
    full_set: EUSRFullSet
    subsets: list[EUSRSubset] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# TSR — Transaction Statistics Report
# ---------------------------------------------------------------------------


class TSRTotal(BaseModel):
    """``<Total>``: the report-wide transaction counts (always present)."""

    incoming: int
    outgoing: int


class TSRSubtotal(BaseModel):
    """A single ``<Subtotal type="...">`` breakdown (0..n per report)."""

    type: str
    keys: list[ReportKey] = Field(default_factory=list)
    incoming: int
    outgoing: int


class TransactionStatisticsReport(BaseModel):
    """A parsed TSR document (``urn:fdc:peppol:transaction-statistics-report:1.0``)."""

    customization_id: str
    profile_id: str
    header: ReportHeader
    total: TSRTotal
    subtotals: list[TSRSubtotal] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _local(tag: object) -> str | None:
    """Return the local name of an element tag, or None for comments/PIs
    (whose ``.tag`` is a callable, not a string)."""
    if not isinstance(tag, str):
        return None
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find(parent, local_name: str):
    for el in parent:
        if _local(el.tag) == local_name:
            return el
    return None


def _text_int(parent, local_name: str) -> int:
    el = _find(parent, local_name)
    return int((el.text or "0").strip()) if el is not None else 0


def _parse_header(header_el) -> ReportHeader:
    period_el = _find(header_el, "ReportPeriod")
    period = ReportPeriod(
        start_date=(_find(period_el, "StartDate").text or "").strip(),
        end_date=(_find(period_el, "EndDate").text or "").strip(),
    )
    reporter_el = _find(header_el, "ReporterID")
    reporter = ReporterID(
        scheme_id=reporter_el.get("schemeID", ""), value=(reporter_el.text or "").strip()
    )
    return ReportHeader(report_period=period, reporter_id=reporter)


def _parse_keys(el) -> list[ReportKey]:
    return [
        ReportKey(
            meta_scheme_id=key_el.get("metaSchemeID", ""),
            scheme_id=key_el.get("schemeID", ""),
            value=(key_el.text or "").strip(),
        )
        for key_el in el
        if _local(key_el.tag) == "Key"
    ]


def parse_eusr(xml_bytes: bytes) -> EndUserStatisticsReport:
    """Parse an EUSR document into an `EndUserStatisticsReport`.

    Raises:
        etree.XMLSyntaxError: On malformed XML.
        AttributeError: If required elements (Header, FullSet) are missing —
            run `validate_eusr` first if the input is untrusted.
    """
    root = safe_fromstring(xml_bytes)

    full_set_el = _find(root, "FullSet")
    full_set = EUSRFullSet(
        sending_end_users=_text_int(full_set_el, "SendingEndUsers"),
        receiving_end_users=_text_int(full_set_el, "ReceivingEndUsers"),
        sending_or_receiving_end_users=_text_int(full_set_el, "SendingOrReceivingEndUsers"),
    )

    subsets = []
    for subset_el in root:
        if _local(subset_el.tag) != "Subset":
            continue
        subsets.append(
            EUSRSubset(
                type=subset_el.get("type", ""),
                keys=_parse_keys(subset_el),
                sending_end_users=_text_int(subset_el, "SendingEndUsers"),
                receiving_end_users=_text_int(subset_el, "ReceivingEndUsers"),
                sending_or_receiving_end_users=_text_int(subset_el, "SendingOrReceivingEndUsers"),
            )
        )

    return EndUserStatisticsReport(
        customization_id=(_find(root, "CustomizationID").text or "").strip(),
        profile_id=(_find(root, "ProfileID").text or "").strip(),
        header=_parse_header(_find(root, "Header")),
        full_set=full_set,
        subsets=subsets,
    )


def parse_tsr(xml_bytes: bytes) -> TransactionStatisticsReport:
    """Parse a TSR document into a `TransactionStatisticsReport`.

    Raises:
        etree.XMLSyntaxError: On malformed XML.
        AttributeError: If required elements (Header, Total) are missing —
            run `validate_tsr` first if the input is untrusted.
    """
    root = safe_fromstring(xml_bytes)

    total_el = _find(root, "Total")
    total = TSRTotal(
        incoming=_text_int(total_el, "Incoming"),
        outgoing=_text_int(total_el, "Outgoing"),
    )

    subtotals = []
    for subtotal_el in root:
        if _local(subtotal_el.tag) != "Subtotal":
            continue
        subtotals.append(
            TSRSubtotal(
                type=subtotal_el.get("type", ""),
                keys=_parse_keys(subtotal_el),
                incoming=_text_int(subtotal_el, "Incoming"),
                outgoing=_text_int(subtotal_el, "Outgoing"),
            )
        )

    return TransactionStatisticsReport(
        customization_id=(_find(root, "CustomizationID").text or "").strip(),
        profile_id=(_find(root, "ProfileID").text or "").strip(),
        header=_parse_header(_find(root, "Header")),
        total=total,
        subtotals=subtotals,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_eusr(xml_bytes: bytes) -> ValidationResult:
    """Validate an EUSR document: XSD structure, then Schematron business rules.

    Runs XSD validation first and returns immediately with those findings if
    it fails (Schematron assumes structurally valid input). Schematron
    validation requires the ``[xslt2]`` optional extra.
    """
    xsd_result = XSDValidator(_EUSR_XSD).validate(xml_bytes, profile="eusr", syntax="XML")
    if not xsd_result.is_valid:
        return xsd_result
    schematron = load_schematron_validator(_EUSR_SCHEMATRON)
    return schematron.validate(xml_bytes, profile="eusr", syntax="XML")


def validate_tsr(xml_bytes: bytes) -> ValidationResult:
    """Validate a TSR document: XSD structure, then Schematron business rules.

    Runs XSD validation first and returns immediately with those findings if
    it fails (Schematron assumes structurally valid input). Schematron
    validation requires the ``[xslt2]`` optional extra.
    """
    xsd_result = XSDValidator(_TSR_XSD).validate(xml_bytes, profile="tsr", syntax="XML")
    if not xsd_result.is_valid:
        return xsd_result
    schematron = load_schematron_validator(_TSR_SCHEMATRON)
    return schematron.validate(xml_bytes, profile="tsr", syntax="XML")


def peppol_reporting_validator(kind: str) -> BaseStructuredValidator:
    """Return a Schematron-only validator for "eusr" or "tsr".

    Mirrors `mcp_einvoicing_core.schematron_artifacts.en16931_base_schematron_validator`'s
    factory shape. Prefer `validate_eusr`/`validate_tsr` for full XSD+Schematron
    validation; use this when only the Schematron pass is wanted (e.g. the
    caller already XSD-validated the document).
    """
    paths = {"eusr": _EUSR_SCHEMATRON, "tsr": _TSR_SCHEMATRON}
    if kind not in paths:
        raise ValueError(f"Unknown reporting kind {kind!r}: expected 'eusr' or 'tsr'.")
    return load_schematron_validator(paths[kind])


# ---------------------------------------------------------------------------
# Bundled code lists
# ---------------------------------------------------------------------------

_EUSR_CODELISTS = {
    "iso3166": "ISO3166",
    "reporter_id_scheme": "ReporterIDScheme",
    "subset_key_meta_scheme": "SubsetKeyMetaScheme",
    "subset_type": "SubsetType",
}
_TSR_CODELISTS = {
    "iso3166": "ISO3166",
    "reporter_id_scheme": "ReporterIDScheme",
    "subtotal_key_meta_scheme": "SubtotalKeyMetaScheme",
    "subtotal_type": "SubtotalType",
}


def load_eusr_codelist(name: str) -> CodeList:
    """Load a bundled EUSR genericode list: "iso3166", "reporter_id_scheme",
    "subset_key_meta_scheme", or "subset_type"."""
    return parse_genericode((_EUSR_CODELIST_DIR / f"{_EUSR_CODELISTS[name]}.gc").read_bytes())


def load_tsr_codelist(name: str) -> CodeList:
    """Load a bundled TSR genericode list: "iso3166", "reporter_id_scheme",
    "subtotal_key_meta_scheme", or "subtotal_type"."""
    return parse_genericode((_TSR_CODELIST_DIR / f"{_TSR_CODELISTS[name]}.gc").read_bytes())
