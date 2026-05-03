"""Profile and syntax registry for mcp-einvoicing-core.

Provides a central registry that maps (country, profile_name, syntax) to
the canonical GuidelineID URN (BT-24 value).  Country packages register
their profiles at import time; tool handlers query the registry to validate
conversion paths and look up URNs.

Usage in a country package (e.g. at the bottom of models/zugferd.py):

    from mcp_einvoicing_core.profile_registry import profile_registry

    profile_registry.register("DE", "MINIMUM",  "CII",
        "urn:factur-x.eu:1p0:minimum")
    profile_registry.register("DE", "EN_16931", "CII",
        "urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:en16931")
    profile_registry.register("DE", "XRECHNUNG", "CII",
        "urn:cen.eu:en16931:2017#compliant#urn:xoev-de:kosit:standard:xrechnung_2.3")
    profile_registry.register("DE", "XRECHNUNG", "UBL",
        "urn:cen.eu:en16931:2017#compliant#urn:xoev-de:kosit:standard:xrechnung_2.3")

Usage in a tool handler:

    from mcp_einvoicing_core.profile_registry import profile_registry

    urn = profile_registry.get_guideline_id("DE", "XRECHNUNG", "CII")
    valid = profile_registry.is_registered("DE", target_profile, target_syntax)
    paths = profile_registry.valid_conversions("DE", "EN_16931", "CII")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProfileEntry:
    """A single (country, profile, syntax) → guideline_id mapping."""

    country: str
    profile_name: str
    syntax: str
    guideline_id: str


class ProfileRegistry:
    """Central registry of e-invoicing profiles and their GuidelineID URNs.

    Structure: {country: {profile_name: {syntax: guideline_id}}}

    Thread-safety: registration happens at module import time (single-threaded);
    all subsequent access is read-only.  No locking is needed.
    """

    def __init__(self) -> None:
        # {country: {profile_name: {syntax: guideline_id}}}
        self._data: dict[str, dict[str, dict[str, str]]] = {}

    # ── Registration ─────────────────────────────────────────────────────────

    def register(
        self,
        country: str,
        profile_name: str,
        syntax: str,
        guideline_id: str,
    ) -> None:
        """Register a (country, profile, syntax) → guideline_id mapping.

        Silently overwrites any existing entry for the same triple.

        Args:
            country:      ISO 3166-1 alpha-2 country code (e.g. "DE", "BE").
            profile_name: Profile identifier used in the DE/BE/IT packages
                          (e.g. "MINIMUM", "EN_16931", "XRECHNUNG").
            syntax:       XML syntax binding (e.g. "CII", "UBL").
            guideline_id: BT-24 URN value for this (profile, syntax) combination.
        """
        self._data.setdefault(country, {}).setdefault(profile_name, {})[syntax] = guideline_id
        logger.debug(
            "ProfileRegistry: registered %s/%s/%s → %s",
            country, profile_name, syntax, guideline_id,
        )

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_guideline_id(
        self, country: str, profile_name: str, syntax: str
    ) -> str | None:
        """Return the GuidelineID URN for a given (country, profile, syntax), or None."""
        return self._data.get(country, {}).get(profile_name, {}).get(syntax)

    def is_registered(self, country: str, profile_name: str, syntax: str) -> bool:
        """True if this (country, profile, syntax) combination is registered."""
        return syntax in self._data.get(country, {}).get(profile_name, {})

    def list_profiles(self, country: str) -> list[str]:
        """Return all registered profile names for a country (sorted)."""
        return sorted(self._data.get(country, {}).keys())

    def list_syntaxes(self, country: str, profile_name: str) -> list[str]:
        """Return all registered syntaxes for a (country, profile) pair (sorted)."""
        return sorted(self._data.get(country, {}).get(profile_name, {}).keys())

    def list_countries(self) -> list[str]:
        """Return all registered country codes (sorted)."""
        return sorted(self._data.keys())

    def valid_conversions(
        self, country: str, from_profile: str, from_syntax: str
    ) -> list[tuple[str, str]]:
        """Return all (to_profile, to_syntax) pairs reachable from the given source.

        A conversion is considered valid when both the source and target are
        registered for the same country.  Profile downgrade safety (data-loss
        risk) is not checked here — that is the tool handler's responsibility.
        """
        if not self.is_registered(country, from_profile, from_syntax):
            return []
        return [
            (profile, syntax)
            for profile, syntaxes in self._data.get(country, {}).items()
            for syntax in syntaxes
            if not (profile == from_profile and syntax == from_syntax)
        ]

    def all_entries(self, country: str | None = None) -> list[ProfileEntry]:
        """Return all registered entries, optionally filtered by country."""
        result: list[ProfileEntry] = []
        for c, profiles in self._data.items():
            if country is not None and c != country:
                continue
            for p, syntaxes in profiles.items():
                for s, gid in syntaxes.items():
                    result.append(ProfileEntry(country=c, profile_name=p, syntax=s, guideline_id=gid))
        return result


# ---------------------------------------------------------------------------
# Module-level singleton — country packages call profile_registry.register(...)
# ---------------------------------------------------------------------------

profile_registry: ProfileRegistry = ProfileRegistry()
