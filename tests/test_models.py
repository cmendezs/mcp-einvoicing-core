from mcp_einvoicing_core.models import (
    _BR_CNPJ_WEIGHTS_1,
    _BR_CNPJ_WEIGHTS_2,
    _br_check_digit,
    TaxIdentifier,
)


class TestValidateBrCpf:
    def test_valid_cpf(self) -> None:
        ok, error = TaxIdentifier.validate_br_cpf("529.982.247-25")
        assert ok is True
        assert error == ""

    def test_wrong_length(self) -> None:
        ok, error = TaxIdentifier.validate_br_cpf("123456789")
        assert ok is False
        assert "11 digits" in error

    def test_all_repeated_digits_rejected(self) -> None:
        ok, error = TaxIdentifier.validate_br_cpf("111.111.111-11")
        assert ok is False
        assert "repeated digit" in error

    def test_bad_check_digits(self) -> None:
        ok, error = TaxIdentifier.validate_br_cpf("529.982.247-26")
        assert ok is False
        assert "check digits" in error


class TestValidateBrCnpj:
    def test_valid_legacy_numeric_cnpj(self) -> None:
        ok, error = TaxIdentifier.validate_br_cnpj("11.222.333/0001-81")
        assert ok is True
        assert error == ""

    def test_wrong_length(self) -> None:
        ok, error = TaxIdentifier.validate_br_cnpj("123456789")
        assert ok is False
        assert "14 characters" in error

    def test_bad_check_digits(self) -> None:
        ok, error = TaxIdentifier.validate_br_cnpj("11.222.333/0001-82")
        assert ok is False
        assert "check digits" in error

    def test_alphanumeric_cnpj_unverified_algorithm(self) -> None:
        # [Unverified]: pins current behavior of the ord(char)-48 mod-11
        # algorithm pending NT Conjunta DFe 2025.001; not a regulatory claim.
        base = "12ABC34501DE"
        check1 = _br_check_digit(base, _BR_CNPJ_WEIGHTS_1)
        check2 = _br_check_digit(base + str(check1), _BR_CNPJ_WEIGHTS_2)
        candidate = f"{base}{check1}{check2}"

        ok, error = TaxIdentifier.validate_br_cnpj(candidate)
        assert ok is True
        assert error == ""

    def test_non_alphanumeric_base_rejected(self) -> None:
        ok, error = TaxIdentifier.validate_br_cnpj("12.34#.567/0001-99")
        assert ok is False
        assert "alphanumeric" in error
