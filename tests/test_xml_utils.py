"""Tests for mcp_einvoicing_core.xml_utils."""

from __future__ import annotations

import base64
from decimal import Decimal

import pytest

from mcp_einvoicing_core.xml_utils import (
    filter_empty_values,
    format_amount,
    format_error,
    format_quantity,
    resolve_xml_input,
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
