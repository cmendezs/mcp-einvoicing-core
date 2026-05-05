"""Tests for mcp_einvoicing_core.profile_registry."""

from __future__ import annotations

import pytest

from mcp_einvoicing_core.profile_registry import ProfileRegistry


@pytest.fixture()
def registry() -> ProfileRegistry:
    r = ProfileRegistry()
    r.register("DE", "MINIMUM", "CII", "urn:factur-x.eu:1p0:minimum")
    r.register("DE", "EN_16931", "CII", "urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:en16931")
    r.register("DE", "XRECHNUNG", "CII", "urn:cen.eu:en16931:2017#compliant#urn:xoev-de:kosit:standard:xrechnung_2.3")
    r.register("DE", "XRECHNUNG", "UBL", "urn:cen.eu:en16931:2017#compliant#urn:xoev-de:kosit:standard:xrechnung_2.3")
    r.register("BE", "PEPPOL_BIS_3", "UBL", "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0")
    return r


class TestRegisterAndGet:
    def test_get_registered_guideline_id(self, registry: ProfileRegistry) -> None:
        result = registry.get_guideline_id("DE", "MINIMUM", "CII")
        assert result == "urn:factur-x.eu:1p0:minimum"

    def test_get_unknown_country_returns_none(self, registry: ProfileRegistry) -> None:
        assert registry.get_guideline_id("FR", "MINIMUM", "CII") is None

    def test_get_unknown_profile_returns_none(self, registry: ProfileRegistry) -> None:
        assert registry.get_guideline_id("DE", "UNKNOWN", "CII") is None

    def test_get_unknown_syntax_returns_none(self, registry: ProfileRegistry) -> None:
        assert registry.get_guideline_id("DE", "MINIMUM", "UBL") is None

    def test_overwrite_silently(self, registry: ProfileRegistry) -> None:
        registry.register("DE", "MINIMUM", "CII", "urn:new-value")
        assert registry.get_guideline_id("DE", "MINIMUM", "CII") == "urn:new-value"


class TestIsRegistered:
    def test_registered_triple(self, registry: ProfileRegistry) -> None:
        assert registry.is_registered("DE", "XRECHNUNG", "UBL") is True

    def test_unregistered_syntax(self, registry: ProfileRegistry) -> None:
        assert registry.is_registered("DE", "MINIMUM", "UBL") is False

    def test_unregistered_country(self, registry: ProfileRegistry) -> None:
        assert registry.is_registered("PL", "ANYTHING", "CII") is False


class TestListMethods:
    def test_list_countries(self, registry: ProfileRegistry) -> None:
        assert registry.list_countries() == ["BE", "DE"]

    def test_list_profiles_for_country(self, registry: ProfileRegistry) -> None:
        assert registry.list_profiles("DE") == ["EN_16931", "MINIMUM", "XRECHNUNG"]

    def test_list_profiles_unknown_country(self, registry: ProfileRegistry) -> None:
        assert registry.list_profiles("XX") == []

    def test_list_syntaxes(self, registry: ProfileRegistry) -> None:
        assert registry.list_syntaxes("DE", "XRECHNUNG") == ["CII", "UBL"]

    def test_list_syntaxes_unknown(self, registry: ProfileRegistry) -> None:
        assert registry.list_syntaxes("DE", "NOPE") == []


class TestValidConversions:
    def test_conversions_from_registered_source(self, registry: ProfileRegistry) -> None:
        paths = registry.valid_conversions("DE", "MINIMUM", "CII")
        assert len(paths) > 0
        assert ("MINIMUM", "CII") not in paths

    def test_no_conversions_from_unregistered_source(self, registry: ProfileRegistry) -> None:
        assert registry.valid_conversions("DE", "MINIMUM", "UBL") == []

    def test_source_excluded_from_results(self, registry: ProfileRegistry) -> None:
        paths = registry.valid_conversions("DE", "EN_16931", "CII")
        assert ("EN_16931", "CII") not in paths


class TestAllEntries:
    def test_all_entries_count(self, registry: ProfileRegistry) -> None:
        assert len(registry.all_entries()) == 5

    def test_filtered_by_country(self, registry: ProfileRegistry) -> None:
        de_entries = registry.all_entries(country="DE")
        assert len(de_entries) == 4
        assert all(e.country == "DE" for e in de_entries)

    def test_entry_fields(self, registry: ProfileRegistry) -> None:
        entries = registry.all_entries(country="BE")
        assert len(entries) == 1
        e = entries[0]
        assert e.country == "BE"
        assert e.profile_name == "PEPPOL_BIS_3"
        assert e.syntax == "UBL"
        assert "peppol" in e.guideline_id

    def test_unknown_country_filter(self, registry: ProfileRegistry) -> None:
        assert registry.all_entries(country="ZZ") == []
