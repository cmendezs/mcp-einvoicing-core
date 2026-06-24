"""Tests for RoutingIdentifier validators.

Test cases ported from mcp-einvoicing-de Leitweg-ID test fixtures.
"""

from mcp_einvoicing_core.routing import RoutingIdentifier


class TestValidateDeLeitweg:
    def test_valid_with_instanz(self) -> None:
        result = RoutingIdentifier.validate_de_leitweg("04011000-12345-03")
        assert result.valid is True
        assert result.error == ""

    def test_valid_short(self) -> None:
        result = RoutingIdentifier.validate_de_leitweg("991-01-03")
        assert result.valid is True

    def test_invalid_format(self) -> None:
        result = RoutingIdentifier.validate_de_leitweg("not-a-leitweg")
        assert result.valid is False
        assert "format" in result.error.lower()

    def test_invalid_check_digit(self) -> None:
        result = RoutingIdentifier.validate_de_leitweg("991-1234512345-06")
        assert result.valid is False
        assert "check digit" in result.error.lower()

    def test_empty_string(self) -> None:
        result = RoutingIdentifier.validate_de_leitweg("")
        assert result.valid is False

    def test_too_long_verwaltungsebene(self) -> None:
        result = RoutingIdentifier.validate_de_leitweg("1234567890123-00")
        assert result.valid is False
