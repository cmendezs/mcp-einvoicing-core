"""Routing identifier validators for government-assigned invoice routing IDs.

Mirrors the ``TaxIdentifier`` pattern: a class with static validators, each
returning a ``RoutingIdValidationResult`` with success/failure, normalized
value, and error message.

Currently contains:
- ``validate_de_leitweg``: German Leitweg-ID (BT-10 for XRechnung B2G)

Future additions (when second-package implementations arrive):
- BE OGM/VCS (gated on [BE-TL-4])

Authority references:
- Leitweg-ID: KoSIT, https://www.xoev.de/publikationen-2316
- Check-digit algorithm: ISO 7064 MOD 97-10

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
