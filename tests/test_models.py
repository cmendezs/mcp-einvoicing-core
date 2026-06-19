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


class TestValidatePlNip:
    def test_valid_nip(self) -> None:
        ok, error = TaxIdentifier.validate_pl_nip("123-456-32-18")
        assert ok is True
        assert error == ""

    def test_wrong_length(self) -> None:
        ok, error = TaxIdentifier.validate_pl_nip("12345")
        assert ok is False
        assert "10 digits" in error

    def test_bad_check_digit(self) -> None:
        ok, error = TaxIdentifier.validate_pl_nip("1234563219")
        assert ok is False
        assert "mismatch" in error


class TestValidatePlRegon:
    def test_valid_9_digit(self) -> None:
        ok, error = TaxIdentifier.validate_pl_regon("123456785")
        assert ok is True
        assert error == ""

    def test_valid_14_digit(self) -> None:
        ok, error = TaxIdentifier.validate_pl_regon("12345678512347")
        assert ok is True
        assert error == ""

    def test_wrong_length(self) -> None:
        ok, error = TaxIdentifier.validate_pl_regon("12345")
        assert ok is False
        assert "9 or 14" in error

    def test_bad_check_digit(self) -> None:
        ok, error = TaxIdentifier.validate_pl_regon("123456786")
        assert ok is False
        assert "mismatch" in error


class TestValidateDeVat:
    def test_valid_with_prefix(self) -> None:
        ok, error = TaxIdentifier.validate_de_vat("DE136695976")
        assert ok is True
        assert error == ""

    def test_valid_without_prefix(self) -> None:
        ok, error = TaxIdentifier.validate_de_vat("136695976")
        assert ok is True
        assert error == ""

    def test_wrong_length(self) -> None:
        ok, error = TaxIdentifier.validate_de_vat("DE12345")
        assert ok is False
        assert "9 digits" in error

    def test_bad_check_digit(self) -> None:
        ok, error = TaxIdentifier.validate_de_vat("DE136695977")
        assert ok is False
        assert "mismatch" in error


class TestValidateBeVat:
    def test_valid_with_prefix(self) -> None:
        ok, error = TaxIdentifier.validate_be_vat("BE0202239951")
        assert ok is True
        assert error == ""

    def test_valid_without_prefix(self) -> None:
        ok, error = TaxIdentifier.validate_be_vat("0202239951")
        assert ok is True
        assert error == ""

    def test_wrong_first_digit(self) -> None:
        ok, error = TaxIdentifier.validate_be_vat("2202239951")
        assert ok is False
        assert "first digit" in error

    def test_bad_check_digits(self) -> None:
        ok, error = TaxIdentifier.validate_be_vat("BE0202239952")
        assert ok is False
        assert "mismatch" in error

    def test_wrong_length(self) -> None:
        ok, error = TaxIdentifier.validate_be_vat("BE12345")
        assert ok is False
        assert "10 digits" in error


class TestValidateEsNif:
    def test_valid_nif(self) -> None:
        ok, error = TaxIdentifier.validate_es_nif("12345678Z")
        assert ok is True
        assert error == ""

    def test_bad_letter(self) -> None:
        ok, error = TaxIdentifier.validate_es_nif("12345678A")
        assert ok is False
        assert "mismatch" in error

    def test_wrong_format(self) -> None:
        ok, error = TaxIdentifier.validate_es_nif("1234567")
        assert ok is False
        assert "8 digits" in error


class TestValidateEsNie:
    def test_valid_nie_x(self) -> None:
        ok, error = TaxIdentifier.validate_es_nie("X1234567L")
        assert ok is True
        assert error == ""

    def test_valid_nie_y(self) -> None:
        ok, error = TaxIdentifier.validate_es_nie("Y1234567X")
        assert ok is True
        assert error == ""

    def test_bad_letter(self) -> None:
        ok, error = TaxIdentifier.validate_es_nie("X1234567A")
        assert ok is False
        assert "mismatch" in error

    def test_wrong_format(self) -> None:
        ok, error = TaxIdentifier.validate_es_nie("A1234567L")
        assert ok is False
        assert "X/Y/Z" in error


class TestValidateEsCif:
    def test_valid_cif_digit_control(self) -> None:
        ok, error = TaxIdentifier.validate_es_cif("A58818501")
        assert ok is True
        assert error == ""

    def test_valid_cif_letter_control(self) -> None:
        ok, error = TaxIdentifier.validate_es_cif("P5765336B")
        assert ok is True
        assert error == ""

    def test_bad_control(self) -> None:
        ok, error = TaxIdentifier.validate_es_cif("A58818502")
        assert ok is False
        assert "mismatch" in error

    def test_wrong_format(self) -> None:
        ok, error = TaxIdentifier.validate_es_cif("Z1234567A")
        assert ok is False
        assert "org letter" in error


class TestValidateFrSiren:
    def test_valid_siren(self) -> None:
        ok, error = TaxIdentifier.validate_fr_siren("732829320")
        assert ok is True
        assert error == ""

    def test_wrong_length(self) -> None:
        ok, error = TaxIdentifier.validate_fr_siren("12345")
        assert ok is False
        assert "9 digits" in error

    def test_bad_checksum(self) -> None:
        ok, error = TaxIdentifier.validate_fr_siren("732829321")
        assert ok is False
        assert "Luhn" in error


class TestValidateFrSiret:
    def test_valid_siret(self) -> None:
        ok, error = TaxIdentifier.validate_fr_siret("73282932000074")
        assert ok is True
        assert error == ""

    def test_wrong_length(self) -> None:
        ok, error = TaxIdentifier.validate_fr_siret("12345")
        assert ok is False
        assert "14 digits" in error

    def test_bad_checksum(self) -> None:
        ok, error = TaxIdentifier.validate_fr_siret("73282932000075")
        assert ok is False
        assert "Luhn" in error


class TestValidateItCodiceFiscale:
    def test_valid_codice_fiscale(self) -> None:
        ok, error = TaxIdentifier.validate_it_codice_fiscale("RSSMRA85M01H501Q")
        assert ok is True
        assert error == ""

    def test_wrong_format(self) -> None:
        ok, error = TaxIdentifier.validate_it_codice_fiscale("12345")
        assert ok is False
        assert "16 characters" in error

    def test_bad_check_letter(self) -> None:
        ok, error = TaxIdentifier.validate_it_codice_fiscale("RSSMRA85M01H501A")
        # Correct check letter is Q, so A should fail
        assert ok is False
        assert "mismatch" in error
