"""CII / UBL wire format conversion via the EN 16931 semantic model.

Composes the four existing primitives (``EN16931UBLSerializer``,
``EN16931UBLParser``, ``EN16931CIISerializer``, ``EN16931CIIParser``)
into a single helper that accepts XML bytes in one syntax and returns
XML bytes in the other.

Round-trip path::

    CII bytes -> EN16931CIIParser.parse() -> EN16931Invoice
              -> EN16931UBLSerializer.serialize() -> UBL bytes

Usage::

    from mcp_einvoicing_core.convert import Syntax, convert_wire_format

    ubl_bytes = convert_wire_format(cii_xml, target=Syntax.UBL)
    cii_bytes = convert_wire_format(ubl_xml, target=Syntax.CII)
"""

from __future__ import annotations

from enum import Enum

from mcp_einvoicing_core.wire_formats import (
    EN16931CIIParser,
    EN16931CIISerializer,
    EN16931UBLParser,
    EN16931UBLSerializer,
)


class Syntax(str, Enum):
    """Target wire format syntax."""

    UBL = "UBL"
    CII = "CII"


def convert_wire_format(xml_bytes: bytes, *, target: Syntax) -> bytes:
    """Convert EN 16931 XML between UBL 2.1 and CII UN/CEFACT.

    Auto-detects the source syntax by probing the root element name,
    then parses to ``EN16931Invoice`` and serialises to the target syntax.

    Args:
        xml_bytes: Source XML document (UBL Invoice/CreditNote or CII CrossIndustryInvoice).
        target: The desired output syntax.

    Returns:
        XML bytes in the target syntax.

    Raises:
        ValueError: If the source syntax cannot be detected or matches the target.
    """
    source = _detect_syntax(xml_bytes)
    if source == target:
        raise ValueError(
            f"Source document is already in {target.value} syntax. "
            "No conversion needed."
        )

    if source == Syntax.CII:
        invoice = EN16931CIIParser().parse(xml_bytes)
        return EN16931UBLSerializer().serialize(invoice)
    else:
        invoice = EN16931UBLParser().parse(xml_bytes)
        return EN16931CIISerializer().serialize(invoice)


def _detect_syntax(xml_bytes: bytes) -> Syntax:
    """Detect whether xml_bytes is UBL or CII by scanning for root element markers."""
    header = xml_bytes[:2000]
    if b"CrossIndustryInvoice" in header:
        return Syntax.CII
    if b"Invoice" in header or b"CreditNote" in header:
        return Syntax.UBL
    raise ValueError(
        "Cannot detect source syntax: root element is neither "
        "CrossIndustryInvoice (CII) nor Invoice/CreditNote (UBL)."
    )
