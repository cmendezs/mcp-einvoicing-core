"""Tests for the Peppol Directory REST search client (CORE-PEPPOL-DIR-1).

asyncio_mode = "auto" (pyproject.toml), no @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import pytest

from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.peppol import PeppolEnvironment
from mcp_einvoicing_core.peppol.directory import (
    PeppolDirectoryClient,
    parse_directory_search_response,
)

# Real response shape confirmed live against
# https://test-directory.peppol.eu/search/1.0/json on 2026-08-23 (see
# mcp_einvoicing_core.peppol.directory module docstring).
_SAMPLE_RESPONSE = {
    "version": "1.0",
    "total-result-count": 2,
    "used-result-count": 2,
    "result-page-index": 0,
    "result-page-count": 20,
    "first-result-index": 0,
    "last-result-index": 1,
    "query-terms": "q=acme",
    "creation-dt": "2026-08-23T08:09:01.198940105Z",
    "matches": [
        {
            "participantID": {"scheme": "iso6523-actorid-upis", "value": "0208:0123456789"},
            "docTypes": [
                {
                    "scheme": "busdox-docid-qns",
                    "value": (
                        "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::Invoice"
                        "##urn:cen.eu:en16931:2017#compliant"
                        "#urn:fdc:peppol.eu:2017:poacc:billing:3.0::2.1"
                    ),
                }
            ],
            "entities": [
                {
                    "name": [{"name": "Acme Inc.", "language": "en"}],
                    "countryCode": "BE",
                    "geoInfo": "Acme street 123",
                    "identifiers": [{"scheme": "VAT", "value": "BE0123456789"}],
                    "websites": ["https://acme.example"],
                    "additionalInfo": "Test participant",
                    "regDate": "2020-01-01",
                }
            ],
        },
        {
            "participantID": {"scheme": "iso6523-actorid-upis", "value": "0208:0987654321"},
            "docTypes": [],
            "entities": [],
        },
    ],
}


class TestParseDirectorySearchResponse:
    def test_parses_wrapper_fields(self) -> None:
        result = parse_directory_search_response(_SAMPLE_RESPONSE)
        assert result.version == "1.0"
        assert result.total_result_count == 2
        assert result.used_result_count == 2
        assert result.query_terms == "q=acme"
        assert result.creation_dt == "2026-08-23T08:09:01.198940105Z"

    def test_parses_match_participant_id(self) -> None:
        result = parse_directory_search_response(_SAMPLE_RESPONSE)
        assert result.matches[0].participant_id.scheme == "iso6523-actorid-upis"
        assert result.matches[0].participant_id.value == "0208:0123456789"

    def test_parses_doc_types(self) -> None:
        result = parse_directory_search_response(_SAMPLE_RESPONSE)
        assert len(result.matches[0].doc_types) == 1
        assert result.matches[0].doc_types[0].scheme == "busdox-docid-qns"

    def test_parses_entity_fields(self) -> None:
        result = parse_directory_search_response(_SAMPLE_RESPONSE)
        entity = result.matches[0].entities[0]
        assert entity.names[0].name == "Acme Inc."
        assert entity.names[0].language == "en"
        assert entity.country_code == "BE"
        assert entity.geo_info == "Acme street 123"
        assert entity.identifiers[0].scheme == "VAT"
        assert entity.identifiers[0].value == "BE0123456789"
        assert entity.websites == ["https://acme.example"]
        assert entity.additional_info == "Test participant"
        assert entity.registration_date == "2020-01-01"

    def test_handles_empty_entities_and_doc_types(self) -> None:
        result = parse_directory_search_response(_SAMPLE_RESPONSE)
        assert result.matches[1].doc_types == []
        assert result.matches[1].entities == []

    def test_handles_missing_matches_key(self) -> None:
        result = parse_directory_search_response({"version": "1.0"})
        assert result.matches == []


class TestPeppolDirectoryClientSearch:
    async def test_search_requires_a_query_term(self) -> None:
        client = PeppolDirectoryClient()
        with pytest.raises(ValueError, match="At least one query term"):
            await client.search()

    async def test_search_rejects_non_json_format(self) -> None:
        client = PeppolDirectoryClient()
        with pytest.raises(ValueError, match="fmt='json'"):
            await client.search(q="acme", fmt="xml")

    async def test_search_builds_correct_url_and_params(self, httpx_mock) -> None:
        httpx_mock.add_response(json=_SAMPLE_RESPONSE)
        client = PeppolDirectoryClient(environment=PeppolEnvironment.TEST)

        result = await client.search(q="acme", country="BE", result_page_count=5)

        request = httpx_mock.get_requests()[0]
        assert request.url.host == "test-directory.peppol.eu"
        assert str(request.url.path) == "/search/1.0/json"
        assert request.url.params["q"] == "acme"
        assert request.url.params["country"] == "BE"
        assert request.url.params["resultPageCount"] == "5"
        assert request.url.params["resultPageIndex"] == "0"
        assert result.total_result_count == 2

    async def test_search_production_base_url(self, httpx_mock) -> None:
        httpx_mock.add_response(json=_SAMPLE_RESPONSE)
        client = PeppolDirectoryClient(environment=PeppolEnvironment.PRODUCTION)
        await client.search(q="acme")
        assert httpx_mock.get_requests()[0].url.host == "directory.peppol.eu"

    async def test_search_participant_param(self, httpx_mock) -> None:
        httpx_mock.add_response(json=_SAMPLE_RESPONSE)
        client = PeppolDirectoryClient()
        await client.search(participant="iso6523-actorid-upis::0208:0123456789")
        request = httpx_mock.get_requests()[0]
        assert request.url.params["participant"] == "iso6523-actorid-upis::0208:0123456789"

    async def test_search_raises_platform_error_on_http_error(self, httpx_mock) -> None:
        httpx_mock.add_response(status_code=400, text="Bad Request")
        client = PeppolDirectoryClient()
        with pytest.raises(PlatformError, match="400"):
            await client.search(q="acme")

    async def test_search_retries_on_429_then_succeeds(self, httpx_mock) -> None:
        httpx_mock.add_response(status_code=429, headers={"Retry-After": "0"})
        httpx_mock.add_response(json=_SAMPLE_RESPONSE)
        client = PeppolDirectoryClient(max_retries=1)
        result = await client.search(q="acme")
        assert result.total_result_count == 2
        assert len(httpx_mock.get_requests()) == 2

    async def test_search_gives_up_after_max_retries(self, httpx_mock) -> None:
        httpx_mock.add_response(status_code=503, headers={"Retry-After": "0"})
        httpx_mock.add_response(status_code=503, headers={"Retry-After": "0"})
        client = PeppolDirectoryClient(max_retries=1)
        with pytest.raises(PlatformError, match="503"):
            await client.search(q="acme")
        assert len(httpx_mock.get_requests()) == 2
