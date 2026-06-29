"""Routing identifier validators for government-assigned invoice routing IDs.

Mirrors the ``TaxIdentifier`` pattern: a class with static validators, each
returning a ``RoutingIdValidationResult`` with success/failure, normalized
value, and error message.

Currently contains:
- ``validate_de_leitweg``: German Leitweg-ID (BT-10 for XRechnung B2G)
- ``validate_be_ogm``: Belgian OGM/VCS structured payment reference

Authority references:
- Leitweg-ID: KoSIT, https://www.xoev.de/publikationen-2316
- Check-digit algorithm: ISO 7064 MOD 97-10
- OGM/VCS: Belgian banking standard, modulo-97 check digit

[Inference: mod-97 algorithm matches ISO 7064 MOD 97-10; strip hyphens,
expand letters, verify numeric_value mod 97 == 1.]
"""

from __future__ import annotations

import re
from typing import NamedTuple


class RoutingIdValidationResult(NamedTuple):
    """Result of a routing identifier validation."""

    valid: bool
    normalized_value: str
    error: str


_LEITWEG_PATTERN = re.compile(
    r"^[0-9]{1,12}(-[A-Za-z0-9]{1,30}){0,1}-[0-9]{2}$"
)


def _mod97(s: str) -> int:
    """ISO 7064 MOD 97-10: expand letters (A=10 ... Z=35), compute mod 97."""
    digits = ""
    for ch in s.upper():
        if ch.isdigit():
            digits += ch
        elif ch.isalpha():
            digits += str(ord(ch) - 55)
    return int(digits) % 97


class RoutingIdentifier:
    """Static validators for government-assigned routing identifiers."""

    @staticmethod
    def validate_de_leitweg(value: str) -> RoutingIdValidationResult:
        """Validate a German Leitweg-ID format and ISO 7064 MOD 97-10 check digit.

        Format: ``<Verwaltungsebene>[-<Instanzkennzeichen>]-<Pruefziffer>``
        where Verwaltungsebene is 1-12 digits, Instanzkennzeichen is 0-30
        alphanumeric characters, and Pruefziffer is exactly 2 digits.
        """
        if not _LEITWEG_PATTERN.match(value):
            return RoutingIdValidationResult(
                valid=False,
                normalized_value=value,
                error=(
                    f"Leitweg-ID {value!r} does not match the required format "
                    "'[0-9]{1,12}(-[A-Z0-9]{1,30})?-[0-9]{2}'. "
                    "Expected: <Verwaltungsebene>[-<Instanzkennzeichen>]-<Pruefziffer>."
                ),
            )
        stripped = value.replace("-", "")
        if _mod97(stripped) != 1:
            return RoutingIdValidationResult(
                valid=False,
                normalized_value=value,
                error=(
                    f"Leitweg-ID {value!r} has an invalid check digit "
                    "(ISO 7064 MOD 97-10 remainder must equal 1)."
                ),
            )
        return RoutingIdValidationResult(
            valid=True,
            normalized_value=value,
            error="",
        )

    @staticmethod
    def validate_be_ogm(value: str) -> RoutingIdValidationResult:
        """Validate a Belgian OGM/VCS structured payment reference.

        Accepts both the formatted form (+++xxx/xxxx/xxxcc+++) and bare 12-digit
        form. The last two digits are the modulo-97 check digits: remainder of
        the first 10 digits divided by 97, or 97 when the remainder is 0.

        Returns the normalised +++xxx/xxxx/xxxcc+++ form on success.
        """
        digits = re.sub(r"[+/\s.\-]", "", value)
        if not re.fullmatch(r"\d{12}", digits):
            return RoutingIdValidationResult(
                valid=False,
                normalized_value=value,
                error=(
                    f"Invalid OGM/VCS reference: {value!r}. Expected 12 digits "
                    "(with optional +++xxx/xxxx/xxxcc+++ formatting)."
                ),
            )
        base = int(digits[:10])
        check = int(digits[10:])
        expected = base % 97 or 97
        if check != expected:
            return RoutingIdValidationResult(
                valid=False,
                normalized_value=value,
                error=(
                    f"Invalid OGM/VCS check digit in {value!r}: "
                    f"expected {expected:02d}, got {check:02d}."
                ),
            )
        normalized = f"+++{digits[:3]}/{digits[3:7]}/{digits[7:12]}+++"
        return RoutingIdValidationResult(
            valid=True,
            normalized_value=normalized,
            error="",
        )
