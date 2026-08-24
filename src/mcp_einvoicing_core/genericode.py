"""OASIS Genericode 1.0 parsing, shared by every deployer-supplied code list.

Genericode 1.0 is the XML schema both the OpenPeppol eDEC code lists
(``mcp_einvoicing_core.peppol.codelists``) and the EN 16931 semantic data
element code lists (``mcp_einvoicing_core.en16931_codelists``) are published
in:

    <gc:CodeList><Identification>...</Identification><ColumnSet>...</ColumnSet>
    <SimpleCodeList><Row><Value ColumnRef="..."><SimpleValue>...</SimpleValue>
    </Value>...</Row>...</SimpleCodeList></gc:CodeList>

This module holds the format-level parser only. Neither the eDEC code lists
nor the EN 16931 code lists carry an in-file redistribution grant, so this
package never bundles the underlying ``.gc`` data — each deployment supplies
its own local copy and points an environment variable at the directory
containing it. See the two consuming modules for their respective env vars
and download sources.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mcp_einvoicing_core.xml_utils import safe_fromstring


class CodelistNotConfiguredError(Exception):
    """The relevant env var is unset, not a directory, or a specific code
    list file is not present under it."""


@dataclass
class CodeList:
    """A parsed OASIS Genericode 1.0 code list."""

    short_name: str
    version: str
    canonical_uri: str | None
    canonical_version_uri: str | None
    columns: tuple[str, ...]
    rows: list[dict[str, str | None]] = field(default_factory=list)


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
            "Not a recognizable Genericode 1.0 document (missing Identification or ColumnSet)."
        )

    def _find_text(parent, local_name: str) -> str | None:
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

    rows: list[dict[str, str | None]] = []
    if simple_code_list is not None:
        for row_el in simple_code_list:
            if _local(row_el.tag) != "Row":
                continue
            row: dict[str, str | None] = {}
            for value_el in row_el:
                if _local(value_el.tag) != "Value":
                    continue
                col_ref = value_el.get("ColumnRef")
                if not col_ref:
                    continue
                simple_value: str | None = None
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
