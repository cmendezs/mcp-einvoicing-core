"""Tests for mcp_einvoicing_core.exceptions."""

from __future__ import annotations

import pytest

from mcp_einvoicing_core.exceptions import (
    AuthenticationError,
    DocumentGenerationError,
    EInvoicingError,
    PartyValidationError,
    PlatformError,
    SchematronValidationError,
    ValidationError,
    XSDValidationError,
)


class TestExceptionHierarchy:
    def test_validation_error_is_einvoicing_error(self) -> None:
        assert issubclass(ValidationError, EInvoicingError)

    def test_party_validation_is_validation_error(self) -> None:
        assert issubclass(PartyValidationError, ValidationError)

    def test_xsd_validation_is_validation_error(self) -> None:
        assert issubclass(XSDValidationError, ValidationError)

    def test_schematron_validation_is_validation_error(self) -> None:
        assert issubclass(SchematronValidationError, ValidationError)

    def test_document_generation_is_einvoicing_error(self) -> None:
        assert issubclass(DocumentGenerationError, EInvoicingError)

    def test_authentication_is_einvoicing_error(self) -> None:
        assert issubclass(AuthenticationError, EInvoicingError)

    def test_platform_is_einvoicing_error(self) -> None:
        assert issubclass(PlatformError, EInvoicingError)

    def test_all_catchable_as_einvoicing_error(self) -> None:
        errors = [
            PartyValidationError(["bad name"], "seller"),
            XSDValidationError(["line 1: invalid"]),
            DocumentGenerationError("template missing"),
            AuthenticationError("token expired"),
            PlatformError(502, "gateway error"),
        ]
        for err in errors:
            with pytest.raises(EInvoicingError):
                raise err


class TestPartyValidationError:
    def test_message_includes_role(self) -> None:
        err = PartyValidationError(["missing VAT"], "seller")
        assert "seller" in str(err)
        assert "missing VAT" in str(err)

    def test_default_role(self) -> None:
        err = PartyValidationError(["bad field"])
        assert "party" in str(err)

    def test_errors_attribute(self) -> None:
        err = PartyValidationError(["e1", "e2"], "buyer")
        assert err.errors == ["e1", "e2"]
        assert err.party_role == "buyer"

    def test_multiple_errors_joined(self) -> None:
        err = PartyValidationError(["err1", "err2"], "buyer")
        assert "err1" in str(err)
        assert "err2" in str(err)


class TestXSDValidationError:
    def test_single_error_message(self) -> None:
        err = XSDValidationError(["line 1: element 'Foo' not expected"])
        assert "line 1" in str(err)

    def test_multiple_errors_shows_count(self) -> None:
        err = XSDValidationError(["e1", "e2", "e3"], schema_version="1.6.1")
        assert "3 errors" in str(err)
        assert "1.6.1" in str(err)

    def test_errors_attribute(self) -> None:
        err = XSDValidationError(["e1"])
        assert err.errors == ["e1"]
        assert err.schema_version == "unknown"


class TestPlatformError:
    def test_message_includes_status_code(self) -> None:
        err = PlatformError(503, "service unavailable")
        assert "503" in str(err)
        assert "service unavailable" in str(err)

    def test_optional_error_code(self) -> None:
        err = PlatformError(400, "bad request", error_code="ERR_001")
        assert err.error_code == "ERR_001"
        assert err.status_code == 400

    def test_no_error_code(self) -> None:
        err = PlatformError(404, "not found")
        assert err.error_code is None
