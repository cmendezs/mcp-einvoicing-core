"""Peppol eDEC code list lookup: participant ID schemes, document types,
processes, transport profiles, SPIS use cases.

Unlike most of mcp-einvoicing-core, this module does NOT bundle the
underlying data inside the wheel. The OpenPeppol eDEC Code Lists carry no
in-file redistribution grant, the identical situation already investigated
for the Peppol Schematron overlay (see
context-library/decisions/peppol-schematron-artifact.md, root repo, which
found no redistribution grant for PEPPOL-EN16931-UBL.sch and declined to
bundle it). Shipping these files inside the published wheel would mean core
redistributing OpenPeppol content to every installer without confirmed
rights to do so.

Instead, each deployment supplies its own local copy: download the "as
GeneriCode" export for each artifact from
https://docs.peppol.eu/edelivery/codelists/ and point
EINVOICING_PEPPOL_CODELIST_DIR at the directory containing them. Filenames
are matched by prefix (e.g. "Document-types-*.gc"), so a version bump in the
deployer's directory (v9.7 to v9.8) needs no code change here.

Genericode 1.0 (OASIS) is the XML schema OpenPeppol publishes these in:
<gc:CodeList><Identification>...</Identification><ColumnSet>...</ColumnSet>
<SimpleCodeList><Row><Value ColumnRef="..."><SimpleValue>...</SimpleValue>
</Value>...</Row>...</SimpleCodeList></gc:CodeList>. All five eDEC artifacts
(Document Types, Participant Identifier Schemes, Processes, Transport
Profiles, SPIS Use Case) share this exact shape, just with different
columns, so one parser handles all of them. Verified 2026-08-21 against real
v9.7 eDEC files.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from mcp_einvoicing_core.xml_utils import safe_fromstring

logger = logging.getLogger(__name__)

_ENV_VAR = "EINVOICING_PEPPOL_CODELIST_DIR"

# Codelist name -> filename prefix, matching the OpenPeppol eDEC download
# names exactly (e.g. "Document-types-v9.7.gc").
_CODELIST_PREFIXES: dict[str, str] = {
    "document_types": "Document-types-",
    "participant_id_schemes": "Participant-identifier-schemes-",
    "processes": "Processes-",
    "transport_profiles": "Transport-profiles-",
    "spis_use_case": "SPIS-Use-Case-",
}


class CodelistNotConfiguredError(Exception):
    """EINVOICING_PEPPOL_CODELIST_DIR is unset, not a directory, or a
    specific codelist file is not present under it."""


@dataclass
class CodeList:
    """A parsed OASIS Genericode 1.0 code list."""

    short_name: str
    version: str
    canonical_uri: Optional[str]
    canonical_version_uri: Optional[str]
    columns: tuple[str, ...]
    rows: list[dict[str, Optional[str]]] = field(default_factory=list)


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def parse_genericode(xml_bytes: bytes) -> CodeList:
    """Parse an OASIS Genericode 1.0 document into a CodeList.

    Raises:
        etree.XMLSyntaxError: On malformed XML.
        ValueError: If the document has no recognizable Identification or
            ColumnSet element (not a Genericode 1.0 document).
    """
    root = safe_fromstring(xml_bytes)

    identification = None
    column_set = None
    simple_code_list = None
    for child in root:
        local = _local(child.tag)
        if local == "Identification":
            identification = child
        elif local == "ColumnSet":
            column_set = child
        elif local == "SimpleCodeList":
            simple_code_list = child

    if identification is None or column_set is None:
        raise ValueError(
            "Not a recognizable Genericode 1.0 document (missing "
            "Identification or ColumnSet)."
        )

    def _find_text(parent, local_name: str) -> Optional[str]:
        for el in parent:
            if _local(el.tag) == local_name:
                return (el.text or "").strip() or None
        return None

    short_name = _find_text(identification, "ShortName") or ""
    version = _find_text(identification, "Version") or ""
    canonical_uri = _find_text(identification, "CanonicalUri")
    canonical_version_uri = _find_text(identification, "CanonicalVersionUri")

    columns: list[str] = []
    for el in column_set:
        if _local(el.tag) == "Column":
            col_id = el.get("Id")
            if col_id:
                columns.append(col_id)

    rows: list[dict[str, Optional[str]]] = []
    if simple_code_list is not None:
        for row_el in simple_code_list:
            if _local(row_el.tag) != "Row":
                continue
            row: dict[str, Optional[str]] = {}
            for value_el in row_el:
                if _local(value_el.tag) != "Value":
                    continue
                col_ref = value_el.get("ColumnRef")
                if not col_ref:
                    continue
                simple_value: Optional[str] = None
                for v_child in value_el:
                    if _local(v_child.tag) == "SimpleValue":
                        simple_value = (v_child.text or "").strip()
                        break
                row[col_ref] = simple_value
            rows.append(row)

    return CodeList(
        short_name=short_name,
        version=version,
        canonical_uri=canonical_uri,
        canonical_version_uri=canonical_version_uri,
        columns=tuple(columns),
        rows=rows,
    )


def _codelist_dir() -> Path:
    raw = os.environ.get(_ENV_VAR, "").strip()
    if not raw:
        raise CodelistNotConfiguredError(
            f"{_ENV_VAR} is not set. Peppol eDEC code list tools require a "
            "local copy of the OpenPeppol code lists (not bundled with this "
            "package, no confirmed redistribution rights, see "
            "context-library/decisions/peppol-schematron-artifact.md for the "
            'identical Schematron precedent). Download the "as GeneriCode" '
            "export for each artifact from "
            "https://docs.peppol.eu/edelivery/codelists/ and set "
            f"{_ENV_VAR} to the directory containing them."
        )
    directory = Path(raw)
    if not directory.is_dir():
        raise CodelistNotConfiguredError(f"{_ENV_VAR}={raw!r} is not a directory.")
    return directory


def _find_codelist_file(directory: Path, prefix: str) -> Path:
    matches = sorted(directory.glob(f"{prefix}*.gc"))
    if not matches:
        raise CodelistNotConfiguredError(
            f"No file matching {prefix}*.gc found under {directory}. "
            'Download the "as GeneriCode" export for this artifact from '
            "https://docs.peppol.eu/edelivery/codelists/."
        )
    return matches[-1]  # lexicographically highest version string wins


def load_codelist(name: str) -> CodeList:
    """Load and parse a named eDEC code list from EINVOICING_PEPPOL_CODELIST_DIR.

    Args:
        name: One of "document_types", "participant_id_schemes", "processes",
            "transport_profiles", "spis_use_case".

    Raises:
        KeyError: If *name* is not a recognized codelist name.
        CodelistNotConfiguredError: If the env var is unset, the directory
            does not exist, or no matching file is found under it.
    """
    prefix = _CODELIST_PREFIXES[name]
    directory = _codelist_dir()
    path = _find_codelist_file(directory, prefix)
    return parse_genericode(path.read_bytes())


def _filter_active(rows: list[dict[str, Optional[str]]], active_only: bool) -> list[dict[str, Optional[str]]]:
    if not active_only:
        return rows
    return [r for r in rows if r.get("state") == "active"]


def list_document_type_ids(active_only: bool = True) -> list[dict[str, Optional[str]]]:
    """Return Peppol document type identifier rows (scheme, value, name, state, ...)."""
    return _filter_active(load_codelist("document_types").rows, active_only)


def list_process_ids(active_only: bool = True) -> list[dict[str, Optional[str]]]:
    """Return Peppol process identifier rows (scheme, value, state)."""
    return _filter_active(load_codelist("processes").rows, active_only)


def list_participant_id_schemes(active_only: bool = True) -> list[dict[str, Optional[str]]]:
    """Return Peppol participant identifier scheme rows (schemeid, iso6523, country, state, ...)."""
    return _filter_active(load_codelist("participant_id_schemes").rows, active_only)


def list_transport_profiles(active_only: bool = True) -> list[dict[str, Optional[str]]]:
    """Return Peppol transport profile rows (protocol, profile-id, state, ...)."""
    return _filter_active(load_codelist("transport_profiles").rows, active_only)


def list_spis_use_case_ids(active_only: bool = True) -> list[dict[str, Optional[str]]]:
    """Return Peppol SPIS use case identifier rows (use-case-id, state, ...)."""
    return _filter_active(load_codelist("spis_use_case").rows, active_only)


def check_document_type_id_in_codelist(scheme: str, value: str) -> dict[str, object]:
    """Check whether a (scheme, value) pair is a recognized Peppol document type identifier.

    Searches all entries regardless of state (active/deprecated/removed) so
    a historical document type can still be identified as once-valid.
    """
    for row in load_codelist("document_types").rows:
        if row.get("scheme") == scheme and row.get("value") == value:
            return {"found": True, **row}
    return {"found": False, "scheme": scheme, "value": value}


def check_process_id_in_codelist(scheme: str, value: str) -> dict[str, object]:
    """Check whether a (scheme, value) pair is a recognized Peppol process identifier."""
    for row in load_codelist("processes").rows:
        if row.get("scheme") == scheme and row.get("value") == value:
            return {"found": True, **row}
    return {"found": False, "scheme": scheme, "value": value}


def check_participant_id_scheme_in_codelist(icd: str) -> dict[str, object]:
    """Check whether a 4-digit ISO 6523 ICD code (e.g. "0208") is a recognized
    Peppol participant ID scheme.

    Matches against the codelist's "iso6523" column, the numeric code that
    appears as the scheme half of a Peppol participant ID
    (e.g. "0208:0123456789"). The codelist's own "schemeid" column is a
    separate human-readable mnemonic (e.g. "BE:EN"), not this numeric code.
    """
    for row in load_codelist("participant_id_schemes").rows:
        if row.get("iso6523") == icd:
            return {"found": True, **row}
    return {"found": False, "iso6523": icd}


def get_peppol_codelist_version() -> dict[str, object]:
    """Report the eDEC code list release version(s) currently configured locally.

    Returns a dict with "versions" (codelist name -> version string, for
    each list that loaded successfully) and "errors" (codelist name -> error
    message, for each list that is missing or unreadable).
    """
    versions: dict[str, str] = {}
    errors: dict[str, str] = {}
    for name in _CODELIST_PREFIXES:
        try:
            versions[name] = load_codelist(name).version
        except CodelistNotConfiguredError as exc:
            errors[name] = str(exc)
    return {"versions": versions, "errors": errors}
