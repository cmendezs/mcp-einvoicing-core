"""Tests for mcp_einvoicing_core.xml_utils."""

from __future__ import annotations

import base64
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

import pytest
from lxml import etree

from mcp_einvoicing_core.xml_utils import (
    MAX_XML_BYTES,
    filter_empty_values,
    format_amount,
    format_error,
    format_quantity,
    resolve_xml_input,
    safe_fromstring,
    safe_parser,
    validate_date_iso,
    validate_iban,
    xml_element,
    xml_escape,
    xml_optional,
)


class TestFormatAmount:
    def test_float_two_decimals(self) -> None:
        assert format_amount(1250.0) == "1250.00"

    def test_decimal_input(self) -> None:
        assert format_amount(Decimal("22"), 2) == "22.00"

    def test_string_input(self) -> None:
        assert format_amount("99.9") == "99.90"

    def test_rounding_half_up(self) -> None:
        assert format_amount(1.005, 2) == "1.01"

    def test_zero_decimals(self) -> None:
        assert format_amount(42.6, 0) == "43"

    def test_four_decimals(self) -> None:
        assert format_amount(1.0, 4) == "1.0000"

    # --- ROUND_HALF_EVEN (banker's rounding) ---------------------------------
    # EN 16931 BR-CO-09 and KSeF require ROUND_HALF_EVEN for VAT totals.
    # At the exact midpoint (.5), ROUND_HALF_EVEN rounds to the nearest even digit.

    def test_half_even_rounds_down_when_preceding_digit_even(self) -> None:
        # 2.345 → 2.34 because 4 is even
        assert format_amount(Decimal("2.345"), 2, rounding_mode=ROUND_HALF_EVEN) == "2.34"

    def test_half_even_rounds_up_when_preceding_digit_odd(self) -> None:
        # 2.355 → 2.36 because 6 is even (rounds away from 5)
        assert format_amount(Decimal("2.355"), 2, rounding_mode=ROUND_HALF_EVEN) == "2.36"

    def test_half_even_vat_total_zero_preceding(self) -> None:
        # 10.005 → 10.00 because 0 is even (EN 16931 BR-CO-09 use-case)
        assert format_amount(Decimal("10.005"), 2, rounding_mode=ROUND_HALF_EVEN) == "10.00"

    def test_half_even_vat_total_odd_preceding(self) -> None:
        # 10.015 → 10.02 because 2 is even
        assert format_amount(Decimal("10.015"), 2, rounding_mode=ROUND_HALF_EVEN) == "10.02"

    def test_half_even_non_midpoint_unchanged_vs_half_up(self) -> None:
        # Away from the midpoint both modes agree
        assert format_amount(Decimal("1.234"), 2, rounding_mode=ROUND_HALF_EVEN) == "1.23"
        assert format_amount(Decimal("1.236"), 2, rounding_mode=ROUND_HALF_EVEN) == "1.24"

    def test_explicit_half_up_matches_default(self) -> None:
        # Explicit ROUND_HALF_UP must equal the default behaviour
        result_default = format_amount(Decimal("2.345"), 2)
        result_explicit = format_amount(Decimal("2.345"), 2, rounding_mode=ROUND_HALF_UP)
        assert result_default == result_explicit == "2.35"


class TestFormatQuantity:
    def test_integer_value(self) -> None:
        assert format_quantity(1.0) == "1"

    def test_trailing_zeros_stripped(self) -> None:
        assert format_quantity(1.50000) == "1.5"

    def test_full_precision(self) -> None:
        assert format_quantity(3.14159265) == "3.14159265"

    def test_decimal_input(self) -> None:
        assert format_quantity(Decimal("2.500")) == "2.5"

    def test_string_input(self) -> None:
        assert format_quantity("10.00") == "10"


class TestValidateDateIso:
    def test_valid_date(self) -> None:
        assert validate_date_iso("2026-01-15") is True

    def test_wrong_separator(self) -> None:
        assert validate_date_iso("15/01/2026") is False

    def test_short_year(self) -> None:
        assert validate_date_iso("26-01-15") is False

    def test_empty_string(self) -> None:
        assert validate_date_iso("") is False

    def test_date_with_time(self) -> None:
        assert validate_date_iso("2026-01-15T00:00:00") is False


class TestValidateIban:
    def test_valid_italian_iban(self) -> None:
        assert validate_iban("IT60X0542811101000000123456") is True

    def test_valid_with_spaces(self) -> None:
        assert validate_iban("IT60 X054 2811 1010 0000 0123 456") is True

    def test_invalid_iban(self) -> None:
        assert validate_iban("not-an-iban") is False

    def test_lowercase_accepted(self) -> None:
        assert validate_iban("it60x0542811101000000123456") is True

    def test_empty_string(self) -> None:
        assert validate_iban("") is False


class TestXmlElement:
    def test_simple_element(self) -> None:
        assert xml_element("Name", "Acme") == "<Name>Acme</Name>"

    def test_with_attributes(self) -> None:
        result = xml_element("Amount", "100.00", {"currencyID": "EUR"})
        assert result == '<Amount currencyID="EUR">100.00</Amount>'

    def test_empty_content(self) -> None:
        assert xml_element("Tag", "") == "<Tag></Tag>"


class TestXmlOptional:
    def test_non_empty_value(self) -> None:
        assert xml_optional("Causale", "pro forma") == "<Causale>pro forma</Causale>"

    def test_none_returns_empty(self) -> None:
        assert xml_optional("PECDestinatario", None) == ""

    def test_empty_string_returns_empty(self) -> None:
        assert xml_optional("Tag", "") == ""


class TestXmlEscape:
    def test_ampersand(self) -> None:
        assert xml_escape("A & B") == "A &amp; B"

    def test_less_than(self) -> None:
        assert xml_escape("<tag>") == "&lt;tag&gt;"

    def test_double_quote(self) -> None:
        assert xml_escape('"quoted"') == "&quot;quoted&quot;"

    def test_single_quote(self) -> None:
        assert xml_escape("it's") == "it&apos;s"

    def test_no_special_chars(self) -> None:
        assert xml_escape("plain text") == "plain text"

    def test_all_special_chars(self) -> None:
        result = xml_escape('<a b="c&d\'e">')
        assert "&lt;" in result
        assert "&amp;" in result
        assert "&quot;" in result
        assert "&apos;" in result


class TestFormatError:
    def test_message_only(self) -> None:
        result = format_error("something failed")
        assert result == {"error": "something failed"}

    def test_with_code(self) -> None:
        result = format_error("not found", code="404")
        assert result == {"error": "not found", "code": "404"}


class TestResolveXmlInput:
    def test_content_string(self) -> None:
        xml = "<root/>"
        assert resolve_xml_input(xml, None) == b"<root/>"

    def test_base64_takes_precedence(self) -> None:
        encoded = base64.b64encode(b"<root/>").decode()
        assert resolve_xml_input("<other/>", encoded) == b"<root/>"

    def test_base64_only(self) -> None:
        encoded = base64.b64encode(b"<doc/>").decode()
        assert resolve_xml_input(None, encoded) == b"<doc/>"

    def test_neither_raises(self) -> None:
        with pytest.raises(ValueError, match="Provide either"):
            resolve_xml_input(None, None)

    def test_invalid_base64_raises(self) -> None:
        with pytest.raises(ValueError, match="not valid base64"):
            resolve_xml_input(None, "!!!not-base64!!!")


class TestSafeParser:
    def test_safe_parser_returns_xml_parser(self) -> None:
        parser = safe_parser()
        assert isinstance(parser, etree.XMLParser)

    def test_safe_fromstring_parses_valid_xml(self) -> None:
        root = safe_fromstring(b"<root><child>text</child></root>")
        assert root.tag == "root"
        assert root[0].text == "text"

    def test_xxe_entity_expansion_is_blocked(self) -> None:
        # With resolve_entities=False, lxml parses the document but does NOT
        # read the referenced file.  The entity reference is left unexpanded in
        # the tree so the text content is never populated with file contents.
        xxe_payload = b"""<?xml version="1.0"?>
<!DOCTYPE root [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<root>&xxe;</root>"""
        root = safe_fromstring(xxe_payload)
        # The text of <root> must NOT contain anything from /etc/passwd.
        # On a typical system the file starts with "root:"; we check for ":"
        # as a quick signal that the file was not read.
        text = (root.text or "") + "".join(
            (c.text or "") + (c.tail or "") for c in root
        )
        assert ":" not in text, (
            "XXE protection failed: entity was expanded and file content leaked"
        )

    def test_billion_laughs_is_blocked(self) -> None:
        # With resolve_entities=False entities are NOT expanded so the
        # billion-laughs tree never materialises — no exception and no DoS.
        billion_laughs = b"""<?xml version="1.0"?>
<!DOCTYPE lol [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<root>&lol3;</root>"""
        root = safe_fromstring(billion_laughs)
        # Entity unexpanded: text content should NOT be the repeated string.
        text = root.text or ""
        assert "lollol" not in text, (
            "Billion-laughs protection failed: entity was expanded"
        )

    def test_size_limit_enforced(self) -> None:
        oversized = b"<r>" + b"x" * (MAX_XML_BYTES + 1) + b"</r>"
        with pytest.raises(ValueError, match="MB safety limit"):
            safe_fromstring(oversized)

    def test_malformed_xml_raises(self) -> None:
        with pytest.raises(etree.XMLSyntaxError):
            safe_fromstring(b"<unclosed>")


class TestFilterEmptyValues:
    def test_removes_none(self) -> None:
        assert filter_empty_values({"a": 1, "b": None}) == {"a": 1}

    def test_removes_empty_string(self) -> None:
        assert filter_empty_values({"a": "x", "b": ""}) == {"a": "x"}

    def test_removes_empty_list(self) -> None:
        assert filter_empty_values({"a": [1], "b": []}) == {"a": [1]}

    def test_removes_empty_dict(self) -> None:
        assert filter_empty_values({"a": 1, "b": {}}) == {"a": 1}

    def test_nested_cleanup(self) -> None:
        # The filter checks values before recursion, so a dict that becomes empty
        # after recursion (e.g. {"e": None} → {}) is not removed from the parent.
        data = {"a": 1, "b": None, "c": "", "d": {"e": None}}
        assert filter_empty_values(data) == {"a": 1, "d": {}}

    def test_list_passthrough(self) -> None:
        assert filter_empty_values([1, 2, 3]) == [1, 2, 3]

    def test_scalar_passthrough(self) -> None:
        assert filter_empty_values(42) == 42
