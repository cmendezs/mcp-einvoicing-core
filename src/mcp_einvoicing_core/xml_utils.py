"""
Shared XML and format utilities for mcp-einvoicing-core.

These helpers extract patterns that appear in both existing repos:

  FR (flow_client.py):   XML is not built at tool level; flows are submitted as binary.
                         _raise_for_status → format_error used here instead.
  IT (global_tools.py):  format_amount, format_quantity, xml_element, xml_optional
                         used extensively in generate_fattura_xml / compute_totali.
  IT (body_tools.py):    validate_iban, validate_date_iso used in build_dati_pagamento /
                         build_dati_generali.
  IT (global_tools.py):  filter_empty_values used in export_to_json.

All future country adapters (BE/PL/DE/ES) will reuse these helpers.

[DECISION: No lxml dependency here.] lxml is heavy and only needed for XSD validation
(IT, DE, BE…). Countries that need it declare it in their own pyproject.toml and import
it locally. xml_utils works with plain string manipulation and stdlib xml.etree only.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Numeric formatting (reused in IT compute_totali, add_linea_dettaglio)
# ---------------------------------------------------------------------------


def format_amount(value: float | Decimal | str, decimals: int = 2) -> str:
    """Format a monetary or percentage amount to fixed decimal places.

    >>> format_amount(1250.0)
    '1250.00'
    >>> format_amount(Decimal('22'), 2)
    '22.00'
    """
    quantizer = Decimal("0." + "0" * decimals)
    return str(Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP))


def format_quantity(value: float | Decimal | str, max_decimals: int = 8) -> str:
    """Format a quantity, stripping trailing zeros (FatturaPA PrezzoUnitario / Quantita pattern).

    >>> format_quantity(1.0)
    '1'
    >>> format_quantity(1.50000)
    '1.5'
    >>> format_quantity(3.14159265)
    '3.14159265'
    """
    formatted = f"{Decimal(str(value)):.{max_decimals}f}"
    return formatted.rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# Date validation
# ---------------------------------------------------------------------------


def validate_date_iso(date_str: str) -> bool:
    """Return True if date_str matches YYYY-MM-DD (does not check calendar validity).

    >>> validate_date_iso('2026-01-15')
    True
    >>> validate_date_iso('15/01/2026')
    False
    """
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", date_str))


# ---------------------------------------------------------------------------
# IBAN validation (ISO 13616)
# ---------------------------------------------------------------------------

_IBAN_PATTERN = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{1,30}$")


def validate_iban(iban: str) -> bool:
    """Validate an IBAN: 2-letter country, 2-digit check, 1-30 alphanumeric chars.

    Strips spaces and uppercases before checking.  Does not perform the full
    modulo-97 check (that is country-adapter responsibility).

    >>> validate_iban('IT60X0542811101000000123456')
    True
    >>> validate_iban('not-an-iban')
    False
    """
    return bool(_IBAN_PATTERN.match(iban.replace(" ", "").upper()))


# ---------------------------------------------------------------------------
# XML element building (reused heavily in IT generate_fattura_xml)
# ---------------------------------------------------------------------------


def xml_element(tag: str, content: str, attrs: Optional[dict[str, str]] = None) -> str:
    """Return a single XML element string: <tag attr="val">content</tag>.

    No escaping is performed — callers must escape content if it may contain
    '<', '>', '&', '"' characters (use xml_escape for that).
    """
    attr_str = "".join(f' {k}="{v}"' for k, v in (attrs or {}).items())
    return f"<{tag}{attr_str}>{content}</{tag}>"


def xml_optional(tag: str, value: Optional[str]) -> str:
    """Return xml_element(tag, value) if value is non-empty, otherwise ''.

    >>> xml_optional('Causale', 'pro forma')
    '<Causale>pro forma</Causale>'
    >>> xml_optional('PECDestinatario', None)
    ''
    """
    return xml_element(tag, value) if value else ""


def xml_escape(text: str) -> str:
    """Escape XML special characters in a text value.

    Use this when embedding user-supplied strings (names, addresses, descriptions)
    into raw XML f-string templates.
    """
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# ---------------------------------------------------------------------------
# Error response (standardized across FR and IT)
# ---------------------------------------------------------------------------


def format_error(message: str, code: Optional[str] = None) -> dict[str, str]:
    """Return a standardized MCP tool error response.

    Both existing repos return {"error": "..."} from tools on failure.
    This helper centralizes the pattern and optionally adds a machine-readable code.

    [DECISION: Keep the 'error' key name unchanged for backward compatibility with
     existing Claude Desktop / Cursor configurations that may parse tool outputs.]
    """
    result: dict[str, str] = {"error": message}
    if code:
        result["code"] = code
    return result


# ---------------------------------------------------------------------------
# Dict utilities (reused in IT export_to_json)
# ---------------------------------------------------------------------------


def filter_empty_values(obj: Any) -> Any:
    """Recursively remove None, empty string, empty list, and empty dict values.

    Extracted verbatim from IT global_tools.py export_to_json._filter().
    Country adapters call this before serializing to JSON.

    >>> filter_empty_values({'a': 1, 'b': None, 'c': '', 'd': {'e': None}})
    {'a': 1}
    """
    if isinstance(obj, dict):
        return {
            k: filter_empty_values(v)
            for k, v in obj.items()
            if v is not None and v != "" and v != [] and v != {}
        }
    if isinstance(obj, list):
        return [filter_empty_values(item) for item in obj]
    return obj
