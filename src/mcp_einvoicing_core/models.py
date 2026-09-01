"""
Shared Pydantic v2 models for mcp-einvoicing-core.

These models represent the **country-agnostic** invoice data concepts.
Every country adapter maps its own format (FatturaPA, UBL, Factur-X, ZUGFeRD…)
to and from these models.

Mapping notes:
  IT (FatturaPA):
    TaxIdentifier   → IdFiscaleIVA / CodiceFiscale
    PartyAddress    → Sede (Indirizzo, CAP, Comune, Nazione)
    InvoiceParty    → CedentePrestatore / CessionarioCommittente
    InvoiceLineItem → DettaglioLinee
    VATSummary      → DatiRiepilogo
    PaymentTerms    → DatiPagamento / DettaglioPagamento
    InvoiceDocument → FatturaElettronica (assembled by generate_fattura_xml)

  FR (XP Z12-013):
    InvoiceParty    → company/establishment in Directory Service
    InvoiceDocument → the binary flow submitted via submit_flow
    (FR doesn't decompose invoices into structured fields at MCP tool level — it
     operates on pre-built binary files. These models are used for directory tools.)

[DECISION: Optional country-specific fields use extra Pydantic Field metadata or
 are handled by subclassing in country packages, not by adding nullable fields
 to the base model for each country.]
"""

from __future__ import annotations

import re
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Primitive building blocks
# ---------------------------------------------------------------------------

_BR_CPF_WEIGHTS_1 = list(range(10, 1, -1))
_BR_CPF_WEIGHTS_2 = list(range(11, 1, -1))

_BR_CNPJ_WEIGHTS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_BR_CNPJ_WEIGHTS_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


_ES_NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_ES_CIF_CONTROL_LETTERS = "JABCDEFGHI"

_IT_CF_ODD_MAP: dict[str, int] = {
    "0": 1,
    "1": 0,
    "2": 5,
    "3": 7,
    "4": 9,
    "5": 13,
    "6": 15,
    "7": 17,
    "8": 19,
    "9": 21,
    "A": 1,
    "B": 0,
    "C": 5,
    "D": 7,
    "E": 9,
    "F": 13,
    "G": 15,
    "H": 17,
    "I": 19,
    "J": 21,
    "K": 2,
    "L": 4,
    "M": 18,
    "N": 20,
    "O": 11,
    "P": 3,
    "Q": 6,
    "R": 8,
    "S": 12,
    "T": 14,
    "U": 16,
    "V": 10,
    "W": 22,
    "X": 25,
    "Y": 24,
    "Z": 23,
}
_IT_CF_EVEN_MAP: dict[str, int] = {
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "A": 0,
    "B": 1,
    "C": 2,
    "D": 3,
    "E": 4,
    "F": 5,
    "G": 6,
    "H": 7,
    "I": 8,
    "J": 9,
    "K": 10,
    "L": 11,
    "M": 12,
    "N": 13,
    "O": 14,
    "P": 15,
    "Q": 16,
    "R": 17,
    "S": 18,
    "T": 19,
    "U": 20,
    "V": 21,
    "W": 22,
    "X": 23,
    "Y": 24,
    "Z": 25,
}


def _br_check_digit(value: str, weights: list[int]) -> int:
    total = sum((ord(c) - 48) * w for c, w in zip(value, weights, strict=True))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


#: Valid 2-letter entity-type codes for Singapore "other entities" UENs
#: (LLPs, societies, foreign companies, etc). Ported 2026-08-28 from
#: python-stdnum's stdnum.sg.uen.OTHER_UEN_ENTITY_TYPES — see
#: TaxIdentifier.validate_sg_uen()'s docstring for provenance. Module-level
#: (not a class attribute) because TaxIdentifier is a pydantic BaseModel,
#: where an underscore-prefixed class attribute becomes a ModelPrivateAttr
#: descriptor rather than a plain value.
_SG_UEN_OTHER_ENTITY_TYPES = frozenset(
    {
        "CC", "CD", "CH", "CL", "CM", "CP", "CS", "CX", "DP", "FB", "FC", "FM",
        "FN", "GA", "GB", "GS", "HS", "LL", "LP", "MB", "MC", "MD", "MH", "MM",
        "MQ", "NB", "NR", "PA", "PB", "PF", "RF", "RP", "SM", "SS", "TC", "TU",
        "VH", "XL",
    }
)  # fmt: skip


class TaxIdentifier(BaseModel):
    """A tax / VAT identifier tied to a country.

    Captures the IdFiscaleIVA pattern (IT), NIP (PL), Steuernummer (DE), NIF (ES),
    BTW-nummer (BE) uniformly.

    country_code: ISO 3166-1 alpha-2 (e.g. 'IT', 'FR', 'DE').
    identifier:   The raw tax number string (no spaces, no prefix).
    """

    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    identifier: str = Field(..., min_length=1, max_length=50)

    @field_validator("country_code")
    @classmethod
    def upper_country(cls, v: str) -> str:
        return v.upper()

    @staticmethod
    def validate_it_partita_iva(identifier: str) -> tuple[bool, str]:
        """Validate an Italian Partita IVA (11-digit VAT number).

        Applies the Agenzia delle Entrate modulo-10 control algorithm:
        odd-position digits (0-indexed) are taken as-is; even-position
        digits are doubled (subtract 9 if the result exceeds 9). The final
        digit must equal (10 - sum % 10) % 10.

        Args:
            identifier: Raw VAT string. Whitespace is stripped before checking.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        piva = identifier.strip()
        if not re.match(r"^\d{11}$", piva):
            return False, "Partita IVA must be exactly 11 digits."
        total = 0
        for i, digit in enumerate(piva[:10]):
            d = int(digit)
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        expected = (10 - (total % 10)) % 10
        actual = int(piva[10])
        if expected != actual:
            return False, f"Checksum mismatch: expected {expected}, got {actual}."
        return True, ""

    @staticmethod
    def validate_br_cpf(identifier: str) -> tuple[bool, str]:
        """Validate a Brazilian CPF (11-digit individual taxpayer registry number).

        Applies the standard public-domain two-check-digit modulo-11 algorithm
        (Receita Federal). ``CPF`` is not schema-constrained beyond ``[0-9]{11}``
        (``TCpf`` in ``tiposBasico_v4.00.xsd``).

        Args:
            identifier: Raw CPF string. ``.`` and ``-`` separators are stripped.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        digits = "".join(c for c in identifier if c.isdigit())
        if len(digits) != 11:
            return False, "CPF must be exactly 11 digits."
        if len(set(digits)) == 1:
            return False, "CPF must not consist of a single repeated digit."

        check1 = _br_check_digit(digits[:9], _BR_CPF_WEIGHTS_1)
        check2 = _br_check_digit(digits[:9] + str(check1), _BR_CPF_WEIGHTS_2)
        if digits[9:] != f"{check1}{check2}":
            return False, "CPF check digits do not match."
        return True, ""

    @staticmethod
    def validate_br_cnpj(identifier: str) -> tuple[bool, str]:
        """Validate a Brazilian CNPJ (company taxpayer registry number).

        Accepts both the legacy all-numeric form (``[0-9]{14}``, schema package
        PL_010c) and the alphanumeric form introduced by PL_010d / NT 2026.004
        (``[0-9A-Z]{12}[0-9]{2}``, homologation from 2026-06-01, production from
        2026-07-01, Instrução Normativa RFB nº 2.229/2024).

        ``[Verified locally — NT Conjunta DFe 2025.001 v1.00, §2 worked
        example, p.6]``: the alphanumeric check-digit algorithm below
        (mod-11, weighted, with each character converted via
        ``ord(char) - 48``) matches the primary source's worked example
        ("12.ABC.345/01DE-35"), bundled in the mcp-nfe-br package at
        ``specs/nfe/DFe NTCJ 2025.001_CNPJ Alfa_v1.00.pdf`` and pinned as a
        golden fixture in
        ``mcp-nfe-br/tests/fixtures/cnpj_alfanumerico_ntcj_2025_001.json``.

        Args:
            identifier: Raw CNPJ string. ``.``, ``/``, and ``-`` separators are
                stripped.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        cleaned = "".join(c for c in identifier if c not in ".-/").upper()
        if len(cleaned) != 14:
            return False, "CNPJ must be exactly 14 characters (excluding separators)."

        base, check_digits = cleaned[:12], cleaned[12:]
        if not check_digits.isdigit():
            return False, "CNPJ check digits must be numeric."
        if not all(c.isdigit() or c.isalpha() for c in base):
            return False, "CNPJ base must be alphanumeric."
        if len(set(base)) == 1:
            return False, "CNPJ must not consist of a single repeated character."

        check1 = _br_check_digit(base, _BR_CNPJ_WEIGHTS_1)
        check2 = _br_check_digit(base + str(check1), _BR_CNPJ_WEIGHTS_2)
        if check_digits != f"{check1}{check2}":
            return False, "CNPJ check digits do not match."
        return True, ""

    # --- Poland ---

    @staticmethod
    def validate_pl_nip(identifier: str) -> tuple[bool, str]:
        """Validate a Polish NIP (Numer Identyfikacji Podatkowej).

        10-digit tax identification number with a weighted modulo-11 check digit.
        Weights: [6, 5, 7, 2, 3, 4, 5, 6, 7]. If the weighted sum mod 11 equals
        10, the NIP is invalid (no valid check digit exists for that base).

        Source: Ministerstwo Finansow, https://www.gov.pl/web/finanse

        Args:
            identifier: Raw NIP string. Dashes and spaces are stripped.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        digits = "".join(c for c in identifier if c.isdigit())
        if len(digits) != 10:
            return False, "NIP must be exactly 10 digits."
        weights = [6, 5, 7, 2, 3, 4, 5, 6, 7]
        total = sum(int(d) * w for d, w in zip(digits[:9], weights))
        check = total % 11
        if check == 10:
            return False, "NIP check digit is invalid (remainder equals 10)."
        if check != int(digits[9]):
            return False, f"NIP check digit mismatch: expected {check}, got {digits[9]}."
        return True, ""

    @staticmethod
    def validate_pl_regon(identifier: str) -> tuple[bool, str]:
        """Validate a Polish REGON (Rejestr Gospodarki Narodowej).

        9-digit (single entity) or 14-digit (local unit) national business
        register number with a weighted modulo-11 check digit. If the remainder
        equals 10, the check digit is 0.

        Source: GUS (Glowny Urzad Statystyczny)

        Args:
            identifier: Raw REGON string. Spaces are stripped.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        digits = "".join(c for c in identifier if c.isdigit())
        if len(digits) not in (9, 14):
            return False, "REGON must be exactly 9 or 14 digits."
        if len(digits) == 9:
            weights = [8, 9, 2, 3, 4, 5, 6, 7]
        else:
            weights = [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8]
        total = sum(int(d) * w for d, w in zip(digits[: len(weights)], weights))
        check = total % 11
        if check == 10:
            check = 0
        if check != int(digits[len(weights)]):
            return False, (
                f"REGON check digit mismatch: expected {check}, got {digits[len(weights)]}."
            )
        return True, ""

    # --- Germany ---

    @staticmethod
    def validate_de_vat(identifier: str) -> tuple[bool, str]:
        """Validate a German USt-IdNr (Umsatzsteuer-Identifikationsnummer).

        Format: ``DE`` prefix + 9 digits. The check digit at position 11 is
        computed using the iterative algorithm specified in DIN ISO/IEC 7064
        (two-digit pure system, modulus 11, radix 2), commonly referenced as
        the "DIN 4774" method by the Bundeszentralamt fur Steuern.

        Source: Bundeszentralamt fur Steuern, https://www.bzst.de

        Args:
            identifier: Raw USt-IdNr string. Whitespace stripped; ``DE`` prefix
                is optional (accepted with or without).

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        cleaned = identifier.strip().upper()
        if cleaned.startswith("DE"):
            cleaned = cleaned[2:]
        if not re.match(r"^\d{9}$", cleaned):
            return False, "USt-IdNr must be 'DE' + exactly 9 digits."
        product = 10
        for digit_char in cleaned[:8]:
            total = (int(digit_char) + product) % 10
            if total == 0:
                total = 10
            product = (total * 2) % 11
        check = 11 - product
        if check == 10:
            check = 0
        if check != int(cleaned[8]):
            return False, f"USt-IdNr check digit mismatch: expected {check}, got {cleaned[8]}."
        return True, ""

    # --- Belgium ---

    @staticmethod
    def validate_be_vat(identifier: str) -> tuple[bool, str]:
        """Validate a Belgian BTW-nummer / numero de TVA.

        Format: optional ``BE`` prefix + 10 decimal digits. The first digit is
        ``0`` or ``1``. The last 2 digits equal ``97 - (first_8_digits mod 97)``.

        Source: SPF Finances / FOD Financien, https://finances.belgium.be

        Args:
            identifier: Raw VAT string. Dots, spaces, and ``BE`` prefix stripped.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        cleaned = identifier.strip().upper().replace(".", "").replace(" ", "")
        if cleaned.startswith("BE"):
            cleaned = cleaned[2:]
        if not re.match(r"^\d{10}$", cleaned):
            return False, "Belgian VAT number must be exactly 10 digits (after removing BE prefix)."
        if cleaned[0] not in ("0", "1"):
            return False, f"Belgian VAT first digit must be 0 or 1, got '{cleaned[0]}'."
        base = int(cleaned[:8])
        expected = 97 - (base % 97)
        actual = int(cleaned[8:10])
        if expected != actual:
            return False, (
                f"Belgian VAT check digits mismatch: expected {expected:02d}, got {actual:02d}."
            )
        return True, ""

    # --- Spain ---

    @staticmethod
    def validate_es_nif(identifier: str) -> tuple[bool, str]:
        """Validate a Spanish NIF (Numero de Identificacion Fiscal) for individuals.

        Format: 8 digits + 1 check letter. The letter is looked up from a fixed
        23-character table at position ``(number mod 23)``.

        Source: AEAT, https://www.agenciatributaria.es

        Args:
            identifier: Raw NIF string. Whitespace stripped.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        cleaned = identifier.strip().upper()
        if not re.match(r"^\d{8}[A-Z]$", cleaned):
            return False, "NIF must be 8 digits followed by 1 letter."
        number = int(cleaned[:8])
        expected = _ES_NIF_LETTERS[number % 23]
        actual = cleaned[8]
        if expected != actual:
            return False, f"NIF check letter mismatch: expected '{expected}', got '{actual}'."
        return True, ""

    @staticmethod
    def validate_es_nie(identifier: str) -> tuple[bool, str]:
        """Validate a Spanish NIE (Numero de Identidad de Extranjero).

        Format: ``X``, ``Y``, or ``Z`` + 7 digits + 1 check letter.
        The prefix letter is replaced with 0, 1, or 2 respectively, then
        the standard NIF check letter algorithm is applied.

        Source: AEAT

        Args:
            identifier: Raw NIE string. Whitespace stripped.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        cleaned = identifier.strip().upper()
        if not re.match(r"^[XYZ]\d{7}[A-Z]$", cleaned):
            return False, "NIE must be X/Y/Z + 7 digits + 1 letter."
        prefix_map = {"X": "0", "Y": "1", "Z": "2"}
        number = int(prefix_map[cleaned[0]] + cleaned[1:8])
        expected = _ES_NIF_LETTERS[number % 23]
        actual = cleaned[8]
        if expected != actual:
            return False, f"NIE check letter mismatch: expected '{expected}', got '{actual}'."
        return True, ""

    @staticmethod
    def validate_es_cif(identifier: str) -> tuple[bool, str]:
        """Validate a Spanish CIF (Codigo de Identificacion Fiscal) for companies.

        Format: 1 org-type letter + 7 digits + 1 control character.
        The control character is a digit for some org types (A, B, E, H) and
        a letter for others (K, P, Q, S); the remaining types (C, D, F, G, J,
        N, R, U, V, W) accept either.

        Source: AEAT

        Args:
            identifier: Raw CIF string. Whitespace stripped.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        cleaned = identifier.strip().upper()
        if not re.match(r"^[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]$", cleaned):
            return (
                False,
                "CIF must be 1 org letter + 7 digits + 1 control character (digit or A-J).",
            )
        org_letter = cleaned[0]
        digits_part = cleaned[1:8]
        control = cleaned[8]

        even_sum = sum(int(digits_part[i]) for i in range(1, 7, 2))
        odd_sum = 0
        for i in range(0, 7, 2):
            doubled = int(digits_part[i]) * 2
            odd_sum += doubled // 10 + doubled % 10
        total = even_sum + odd_sum
        check_digit = (10 - (total % 10)) % 10

        digit_only = {"A", "B", "E", "H"}
        letter_only = {"K", "P", "Q", "S"}

        if org_letter in digit_only:
            if control != str(check_digit):
                return False, (
                    f"CIF control digit mismatch: expected '{check_digit}', got '{control}'."
                )
        elif org_letter in letter_only:
            expected_letter = _ES_CIF_CONTROL_LETTERS[check_digit]
            if control != expected_letter:
                return False, (
                    f"CIF control letter mismatch: expected '{expected_letter}', got '{control}'."
                )
        else:
            expected_letter = _ES_CIF_CONTROL_LETTERS[check_digit]
            if control != str(check_digit) and control != expected_letter:
                return False, (
                    f"CIF control mismatch: expected '{check_digit}' or "
                    f"'{expected_letter}', got '{control}'."
                )
        return True, ""

    # --- France ---

    @staticmethod
    def _luhn_checksum(digits: str) -> int:
        total = 0
        for i, ch in enumerate(reversed(digits)):
            d = int(ch)
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10

    @staticmethod
    def validate_fr_siren(identifier: str) -> tuple[bool, str]:
        """Validate a French SIREN (9-digit company identifier).

        The 9th digit is a Luhn check digit.

        Source: INSEE, https://www.insee.fr

        Args:
            identifier: Raw SIREN string. Spaces stripped.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        digits = "".join(c for c in identifier if c.isdigit())
        if len(digits) != 9:
            return False, "SIREN must be exactly 9 digits."
        if TaxIdentifier._luhn_checksum(digits) != 0:
            return False, "SIREN Luhn checksum failed."
        return True, ""

    @staticmethod
    def validate_fr_siret(identifier: str) -> tuple[bool, str]:
        """Validate a French SIRET (14-digit establishment identifier).

        SIRET = SIREN (9 digits) + NIC (5 digits). The 14th digit is a Luhn
        check digit applied over all 14 digits.

        Source: INSEE, https://www.insee.fr/fr/information/1972216

        Args:
            identifier: Raw SIRET string. Spaces stripped.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        digits = "".join(c for c in identifier if c.isdigit())
        if len(digits) != 14:
            return False, "SIRET must be exactly 14 digits."
        if TaxIdentifier._luhn_checksum(digits) != 0:
            return False, "SIRET Luhn checksum failed."
        return True, ""

    @staticmethod
    def validate_fr_tva_intra(identifier: str) -> tuple[bool, str]:
        """Validate a French TVA intracommunautaire number.

        Format: ``FR`` + 2 check digits + 9-digit SIREN. The check key is
        computed as ``(12 + 3 * (SIREN mod 97)) mod 97``.

        Source: Direction Generale des Finances Publiques (DGFiP),
        Article 286 ter du Code general des impots.

        Args:
            identifier: Raw TVA number. Spaces stripped, case-insensitive.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        cleaned = identifier.replace(" ", "").upper()
        if cleaned.startswith("FR"):
            cleaned = cleaned[2:]
        if len(cleaned) != 11:
            return (
                False,
                "TVA intracommunautaire must be 11 characters after FR prefix (2 check digits + 9-digit SIREN).",
            )
        if not cleaned.isdigit():
            return False, "TVA intracommunautaire must contain only digits after FR prefix."
        check_digits = int(cleaned[:2])
        siren = int(cleaned[2:])
        expected = (12 + 3 * (siren % 97)) % 97
        if check_digits != expected:
            return (
                False,
                f"TVA check key mismatch: expected {expected:02d}, got {check_digits:02d}.",
            )
        return True, ""

    # --- Italy ---

    @staticmethod
    def validate_it_codice_fiscale(identifier: str) -> tuple[bool, str]:
        """Validate an Italian Codice Fiscale (16-character individual tax code).

        Format: 6 letters (surname+given) + 2 digits (year) + 1 letter (month)
        + 2 digits (day+gender) + 4 alphanumeric (municipality) + 1 check letter.
        The check letter is computed by summing odd-position and even-position
        characters (1-indexed) through separate lookup tables, then taking
        ``sum mod 26`` mapped to A-Z.

        Source: Agenzia delle Entrate, DM 12/03/1974

        Args:
            identifier: Raw Codice Fiscale string. Whitespace stripped.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        cleaned = identifier.strip().upper()
        if not re.match(r"^[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z0-9]{4}[A-Z]$", cleaned):
            return False, (
                "Codice Fiscale must be 16 characters: "
                "6 letters + 2 digits + 1 letter + 2 digits + 4 alphanumeric + 1 check letter."
            )
        total = 0
        for i, ch in enumerate(cleaned[:15]):
            if (i + 1) % 2 == 1:
                total += _IT_CF_ODD_MAP[ch]
            else:
                total += _IT_CF_EVEN_MAP[ch]
        expected = chr(ord("A") + (total % 26))
        actual = cleaned[15]
        if expected != actual:
            return False, (
                f"Codice Fiscale check letter mismatch: expected '{expected}', got '{actual}'."
            )
        return True, ""

    # --- United Arab Emirates ---

    @staticmethod
    def validate_ae_trn(identifier: str) -> tuple[bool, str]:
        """Validate the format of a UAE TRN (Tax Registration Number).

        Format: exactly 15 numeric digits (e.g. ``198765432102003``), confirmed
        against PINT AE example invoices
        (``cac:PartyTaxScheme/cbc:CompanyID``, IBT-031/IBT-048).

        The UAE FTA's Peppol Participant Identifier ("TIN") is the first 10
        digits of the TRN — see ``mcp-einvoicing-ae``'s Peppol identifier
        handling for that derivation; it is out of scope for this validator.

        ``[NEED: check-digit algorithm]`` — no checksum/check-digit algorithm
        for the TRN was found in any supplied FTA or Peppol AE specification
        document as of 2026-08-27. This validator checks format only (length
        and digit-only content); it does not and must not claim to verify a
        checksum that has not been confirmed from a primary source. If a
        checksum algorithm is later confirmed, extend this validator rather
        than fabricating one now.

        Source: `context-library/countries/ae.md` (`mcp-einvoicing` monorepo),
        section "TRN (Tax Registration Number)".

        Args:
            identifier: Raw TRN string. Whitespace is stripped before checking.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        trn = identifier.strip()
        if not re.match(r"^\d{15}$", trn):
            return False, "TRN must be exactly 15 digits."
        return True, ""

    # --- Singapore ---

    @staticmethod
    def validate_sg_uen(identifier: str) -> tuple[bool, str]:
        """Validate a Singapore UEN (Unique Entity Number), including its check digit.

        ACRA (Accounting and Corporate Regulatory Authority) defines three UEN
        formats, distinguished by entity type:

          - Businesses (ROB): ``nnnnnnnnX`` — 8 digits + 1 check-alphabet
            letter (9 characters).
          - Local companies (ROC): ``yyyynnnnnX`` — 4-digit registration year
            + 5 digits + 1 check-alphabet letter (10 characters).
          - Other entities (LLPs, societies, foreign companies): ``PyyQRnnnnX``
            — a prefix letter (``R``, ``S``, or ``T``) + 2-digit year + a
            2-letter entity-type code (one of ``_SG_UEN_OTHER_ENTITY_TYPES``,
            e.g. ``"LL"``, ``"FC"``) + 4 digits + 1 check-alphabet letter (10
            characters).

        Format source: ACRA UEN structure, supplied by the user 2026-08-27
        (`context-library/countries/sg.md`, "Party-identifier formats").

        Check-digit algorithm source (added 2026-08-28): **ACRA does not
        publish a standalone specification of the check-digit formula** —
        confirmed by the user directly, not assumed. The weights, moduli, and
        check-alphabets below are ported verbatim from `python-stdnum`
        (`stdnum.sg.uen`, https://github.com/arthurdejong/python-stdnum,
        LGPL-2.1), a widely-used open-source identifier-validation library —
        read directly from its installed source (`calc_business_check_digit`,
        `calc_local_company_check_digit`, `calc_other_check_digit`,
        `OTHER_UEN_ENTITY_TYPES`), not reconstructed from memory. This is a
        **third-party reference implementation, not an ACRA-confirmed
        specification** — label any output that depends on it accordingly.
        Test vectors below are `python-stdnum`'s own doctests, which are
        themselves real (or realistically-shaped) UEN values, not fabricated.

        Args:
            identifier: Raw UEN string. Whitespace is stripped before checking.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        uen = identifier.strip().upper()

        if len(uen) == 9:
            if not (uen[:8].isdigit() and uen[8].isalpha()):
                return False, "Business UEN must be 8 digits followed by a check letter."
            weights = (10, 4, 9, 3, 8, 2, 7, 1)
            alphabet = "XMKECAWLJDB"
            check = alphabet[sum(int(n) * w for n, w in zip(uen[:8], weights)) % 11]
            if uen[8] != check:
                return False, f"Invalid check digit for business UEN: expected {check!r}."
            return True, ""

        if len(uen) != 10:
            return False, (
                "UEN must be 9 characters (business) or 10 characters "
                "(local company / other entity)."
            )

        if uen[0].isdigit():
            if not (uen[:9].isdigit() and uen[9].isalpha()):
                return False, "Local company UEN must be 9 digits followed by a check letter."
            weights = (10, 8, 6, 4, 9, 7, 5, 3, 1)
            alphabet = "ZKCMDNERGWH"
            check = alphabet[sum(int(n) * w for n, w in zip(uen[:9], weights)) % 11]
            if uen[9] != check:
                return False, f"Invalid check digit for local company UEN: expected {check!r}."
            return True, ""

        if uen[0] not in ("R", "S", "T"):
            return False, "Other-entity UEN must start with 'R', 'S', or 'T'."
        if not uen[1:3].isdigit():
            return False, "Other-entity UEN characters 2-3 must be the 2-digit issuance year."
        if uen[3:5] not in _SG_UEN_OTHER_ENTITY_TYPES:
            return False, f"Unrecognized other-entity UEN entity-type code: {uen[3:5]!r}."
        if not (uen[5:9].isdigit() and uen[9].isalpha()):
            return False, "Other-entity UEN must end with 4 digits followed by a check letter."
        alphabet = "ABCDEFGHJKLMNPQRSTUVWX0123456789"
        weights = (4, 3, 5, 3, 10, 2, 2, 5, 7)
        try:
            check = alphabet[
                (sum(alphabet.index(n) * w for n, w in zip(uen[:9], weights)) - 5) % 11
            ]
        except ValueError:
            return False, "Other-entity UEN contains a character outside the check-digit alphabet."
        if uen[9] != check:
            return False, f"Invalid check digit for other-entity UEN: expected {check!r}."
        return True, ""

    # --- Mexico ---

    @staticmethod
    def validate_mx_rfc(identifier: str) -> tuple[bool, str]:
        """Validate the format of a Mexican RFC (Registro Federal de Contribuyentes).

        Format: 3-4 uppercase letters (or ``&``/``Ñ``) + 6-digit birth/incorporation
        date (``YYMMDD``) + 3-character homoclave (2 alphanumerics + 1 digit or
        ``A``), for a total length of 12 (moral / legal entities) or 13
        (física / natural persons). Regex ported verbatim from the normative
        ``t_RFC`` simple type in ``tdCFDI.xsd`` (SAT CFDI 4.0 shared types),
        supplied by the user 2026-09-01
        (`context-library/countries/mx.md`, "Party-identifier formats").

        ``[NEED: homoclave check-digit algorithm]`` — no published normative
        source for the RFC homoclave check-character algorithm was found in
        any supplied SAT specification document as of 2026-09-01. Following
        the ``validate_ae_trn`` precedent, this validator checks format only
        (length, character classes, and calendar-plausible date component);
        it does not and must not claim to verify a homoclave that has not
        been confirmed from a primary source. If the algorithm is later
        confirmed, extend this validator rather than fabricating one now.

        Args:
            identifier: Raw RFC string. Whitespace is stripped and the value
                is upper-cased before checking.

        Returns:
            ``(True, "")`` on success, ``(False, error_message)`` on failure.
        """
        rfc = identifier.strip().upper()
        pattern = (
            r"^[A-Z&Ñ]{3,4}"
            r"[0-9]{2}(0[1-9]|1[012])(0[1-9]|[12][0-9]|3[01])"
            r"[A-Z0-9]{2}[0-9A]$"
        )
        if not re.match(pattern, rfc):
            return False, (
                "RFC must be 3-4 letters (or '&'/'Ñ'), a 6-digit YYMMDD date, "
                "and a 3-character homoclave (12 or 13 characters total)."
            )
        return True, ""


class PartyAddress(BaseModel):
    """Postal address of a party's registered office.

    Maps to:
      IT → Sede (Indirizzo / CAP / Comune / Nazione)
      UBL → PostalAddress
      ZUGFeRD → ram:PostalTradeAddress
    """

    street: str = Field(..., description="Street address (via, rue, Straße…)")
    postal_code: str = Field(..., description="Postal / ZIP code")
    city: str = Field(..., description="City / municipality")
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    province: str | None = Field(
        default=None,
        description="Province / region code. Required by IT (Provincia) and ES (Provincia).",
    )
    gln: str | None = Field(
        default=None,
        description="GS1 Global Location Number (13 digits). Emitted in address blocks when present (e.g. KSeF FA(2)/FA(3) <GLN>).",
    )

    @field_validator("country_code")
    @classmethod
    def upper_country(cls, v: str) -> str:
        return v.upper()


# ---------------------------------------------------------------------------
# Party
# ---------------------------------------------------------------------------


class InvoiceParty(BaseModel):
    """Seller (CedentePrestatore / Supplier) or buyer (CessionarioCommittente / Customer).

    Supports both legal entities (name) and natural persons (first_name + last_name).
    At least one of {name} or {first_name + last_name} must be provided.

    tax_id:         Primary VAT/fiscal identifier (required).
    alt_tax_id:     Secondary identifier (e.g. IT CodiceFiscale alongside IdFiscaleIVA).
    address:        Registered office address.
    """

    tax_id: TaxIdentifier
    alt_tax_ids: list[TaxIdentifier] = Field(
        default_factory=list,
        description=(
            "Additional tax identifiers beyond the primary tax_id. "
            "IT: CodiceFiscale alongside IdFiscaleIVA. "
            "ES: NIF when the primary IdFiscale is the EU VAT number. "
            "KSeF cross-border: EU VAT ID when the seller is non-PL. "
            "Use one TaxIdentifier per secondary identifier; order is not significant."
        ),
    )
    name: str | None = Field(default=None, description="Legal entity name (Denominazione)")
    first_name: str | None = Field(default=None, description="First name (natural person)")
    last_name: str | None = Field(default=None, description="Last name (natural person)")
    address: PartyAddress | None = None

    @model_validator(mode="after")
    def check_identity(self) -> InvoiceParty:
        has_entity = bool(self.name)
        has_person = bool(self.first_name and self.last_name)
        if not has_entity and not has_person:
            raise ValueError(
                "Either 'name' (legal entity) or both 'first_name'+'last_name' (natural person) "
                "must be provided."
            )
        if has_entity and (self.first_name or self.last_name):
            raise ValueError("'name' is mutually exclusive with 'first_name'/'last_name'.")
        return self

    @property
    def display_name(self) -> str:
        """Returns name for legal entities, 'FirstName LastName' for persons."""
        if self.name:
            return self.name
        return f"{self.first_name} {self.last_name}"


# ---------------------------------------------------------------------------
# Document body
# ---------------------------------------------------------------------------


class InvoiceLineItem(BaseModel):
    """A single invoice line (DettaglioLinee / cac:InvoiceLine / ram:IncludedSupplyChainTradeLineItem).

    vat_rate: VAT percentage (0.0–100.0). Use 0.0 with vat_exemption_code for exempt lines.
    vat_exemption_code: Country-specific exemption code (IT: N1–N7, DE: S/Z/E, BE: VATEX-EU-...).
    """

    line_number: int = Field(..., ge=1)
    description: str = Field(..., max_length=1000)
    quantity: Decimal | None = Field(default=None, description="Quantity. Omit for lump sums.")
    unit_of_measure: str | None = Field(default=None, max_length=10)
    unit_price: Decimal = Field(..., description="Unit price before VAT")
    total_price: Decimal = Field(..., description="Total line amount before VAT")
    vat_rate: Decimal = Field(default=Decimal("22"), ge=Decimal("0"), le=Decimal("100"))
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    vat_exemption_code: str | None = Field(
        default=None,
        description="Country-specific VAT exemption code. Required when vat_rate is 0.",
    )

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()


class VATSummary(BaseModel):
    """VAT summary entry for a group of lines sharing the same rate.

    Maps to IT DatiRiepilogo, UBL TaxTotal/TaxSubtotal, ZUGFeRD ram:ApplicableTradeTax.
    """

    vat_rate: Decimal = Field(..., ge=Decimal("0"), le=Decimal("100"))
    taxable_base: Decimal = Field(..., description="Net amount subject to this VAT rate")
    vat_amount: Decimal = Field(..., description="VAT amount (taxable_base × vat_rate / 100)")
    vat_exemption_code: str | None = Field(
        default=None,
        description="Exemption code when vat_rate is 0",
    )


class PaymentTerms(BaseModel):
    """Payment terms and method.

    Maps to IT DatiPagamento, UBL PaymentMeans, ZUGFeRD ram:SpecifiedTradePaymentTerms.

    [AMBIGUITY: IT uses structured codes (TP01/02/03 + MP01-23). UBL and ZUGFeRD use
     free-text terms + UNCL4461 payment means codes. The base model uses free-form
     strings to remain format-neutral; country validators enforce their own code sets.]
    Option A: Store raw country codes → simpler, no translation layer needed.
    Option B: Use enums mapped per country → more type-safe but requires maintenance.
    Chosen: Option A (raw strings). Rationale: code sets vary significantly (IT has 23
    payment methods, UBL UNCL4461 has 70+).
    """

    payment_terms_code: str | None = Field(
        default=None,
        description="Country-specific payment terms code (IT: TP01/02/03, ES: contado/plazo)",
    )
    payment_method_code: str = Field(
        ...,
        description="Country-specific payment method code (IT: MP01-23, UBL: UNCL4461)",
    )
    amount: Decimal = Field(..., description="Payment amount")
    due_date: str | None = Field(
        default=None,
        description="Payment due date (YYYY-MM-DD)",
    )
    iban: str | None = Field(
        default=None,
        description="IBAN for bank transfers (validated by xml_utils.validate_iban)",
    )
    bank_name: str | None = Field(
        default=None,
        description="Financial institution name",
    )
    bic: str | None = Field(
        default=None,
        description="BIC/SWIFT code for international transfers",
    )


# ---------------------------------------------------------------------------
# Top-level document
# ---------------------------------------------------------------------------


class InvoiceDocument(BaseModel):
    """Country-agnostic invoice document envelope.

    Country adapters read/write this model via BaseDocumentGenerator.generate()
    and BaseDocumentParser.to_invoice_document().

    document_type: Country-specific code (IT: TD01–TD28, UBL: 380/381/384, DE: RE/GU…).
    transmission_format: Platform routing hint (IT: FPA12/FPR12, FR: B2B/B2BInt/B2C).
    """

    document_type: str = Field(..., description="Country-specific document type code")
    date: str = Field(..., description="Invoice date (YYYY-MM-DD)")
    number: str = Field(..., max_length=50, description="Invoice / document number")
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    transmission_format: str | None = Field(
        default=None,
        description="Platform routing / format hint (FPA12, FPR12, B2B, etc.)",
    )
    seller: InvoiceParty
    buyer: InvoiceParty
    lines: list[InvoiceLineItem] = Field(default_factory=list)
    vat_summary: list[VATSummary] = Field(default_factory=list)
    payment: PaymentTerms | None = None
    note: str | None = Field(
        default=None,
        max_length=1000,
        description="Free-text description/reason (IT: Causale, UBL: Note)",
    )

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------


class TaxIdValidationResult(BaseModel):
    """Typed result returned by BasePartyValidator.validate_tax_id.

    valid:        True when the identifier passed format and checksum checks.
    value:        Cleaned / normalised identifier on success (no spaces, no prefix).
    country_code: ISO 3166-1 alpha-2 country code used for validation.
    error:        Human-readable failure reason when valid is False.
    """

    valid: bool
    value: str | None = None
    country_code: str | None = None
    error: str | None = None

    @classmethod
    def ok(cls, value: str, country_code: str) -> TaxIdValidationResult:
        return cls(valid=True, value=value, country_code=country_code)

    @classmethod
    def fail(cls, error: str, country_code: str | None = None) -> TaxIdValidationResult:
        return cls(valid=False, error=error, country_code=country_code)


class DocumentValidationResult(BaseModel):
    """Output of BaseDocumentValidator.validate().

    valid:    True if the document passed all checks.
    errors:   List of error strings (XSD errors, business rule violations…).
    warnings: Non-blocking issues (deprecated codes, optional field usage…).
    metadata: Format-specific metadata extracted during validation
              (e.g. versione, namespace, schema_version).
    """

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    def to_dict(self) -> dict:
        """Return a plain dict suitable for MCP tool responses."""
        result: dict = {"valid": self.valid, "errors": self.errors}
        if self.warnings:
            result["warnings"] = self.warnings
        if self.metadata:
            result.update(self.metadata)
        return result
