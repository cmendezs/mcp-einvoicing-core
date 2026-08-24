"""Peppol Directory REST search client (CORE-PEPPOL-DIR-1).

Wraps the public, unauthenticated machine-to-machine search interface of the
Peppol Directory (``GET /search/1.0/{format}``), documented in the vendored
"Peppol Directory" specification v1.1.1 (``specs/peppol/PEPPOL-EDN-Directory-1.1.1-2020-10-15.pdf``,
CC BY-NC-ND, non-commercial/no-derivatives use satisfied) section 7.1.

The wrapper-level response fields (``version``, ``total-result-count``, ...)
are normatively documented in that spec's section 7.1.2. The per-match field
names inside ``matches`` (``participantID``, ``docTypes``, ``entities``,
``geoInfo``, ``websites``, ...) are not given as a literal JSON example in
the spec text; they were confirmed live against the public test instance
(https://test-directory.peppol.eu/search/1.0/json) on 2026-08-23.
[Inference: "contacts" as the per-entity contact list key, by analogy with
the vendored ``peppol-directory-business-card-20180621.xsd``'s ``Contact``
element and the plural ``identifiers``/``websites`` keys already confirmed
live — no live example carried a populated contact list to verify directly.]

Base URLs:
    Production: https://directory.peppol.eu
    Test:       https://test-directory.peppol.eu

Rate limiting: the vendored spec does not state a formal rate limit; a
conservative client-side throttle (~2 requests/second) is applied here to
avoid overloading the shared public service, per the roadmap's guidance.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.http_client import compute_retry_delay
from mcp_einvoicing_core.peppol import PeppolEnvironment

logger = logging.getLogger(__name__)

_BASE_URLS = {
    PeppolEnvironment.PRODUCTION: "https://directory.peppol.eu",
    PeppolEnvironment.TEST: "https://test-directory.peppol.eu",
}

_MIN_REQUEST_INTERVAL = 0.5  # ~2 queries/second client-side throttle


class PeppolDirectoryIdentifier(BaseModel):
    """A single scheme-qualified identifier (participant ID or additional identifier)."""

    scheme: str
    value: str


class PeppolDirectoryDocType(BaseModel):
    """A document type identifier supported by a matched participant."""

    scheme: str
    value: str


class PeppolDirectoryName(BaseModel):
    """A single (optionally language-tagged) business entity name."""

    name: str
    language: str | None = None


class PeppolDirectoryContact(BaseModel):
    """A single business contact point.

    [Inference: field presence/naming not confirmed against a live example
    with a populated contact list — see module docstring.]
    """

    type: str | None = None
    name: str | None = None
    phone_number: str | None = None
    email: str | None = None


class PeppolBusinessEntity(BaseModel):
    """A single business entity reachable via a matched participant ID.

    Mapped to ``BusinessEntityType`` in the vendored
    ``peppol-directory-business-card-20180621.xsd``.
    """

    names: list[PeppolDirectoryName] = Field(default_factory=list)
    country_code: str | None = None
    geo_info: str | None = None
    identifiers: list[PeppolDirectoryIdentifier] = Field(default_factory=list)
    websites: list[str] = Field(default_factory=list)
    contacts: list[PeppolDirectoryContact] = Field(default_factory=list)
    additional_info: str | None = None
    registration_date: str | None = None


class PeppolBusinessCard(BaseModel):
    """A single Directory search match: one participant and its business entities."""

    participant_id: PeppolDirectoryIdentifier
    doc_types: list[PeppolDirectoryDocType] = Field(default_factory=list)
    entities: list[PeppolBusinessEntity] = Field(default_factory=list)


class PeppolDirectorySearchResult(BaseModel):
    """Parsed response of a ``GET /search/1.0/json`` Directory search."""

    version: str = ""
    total_result_count: int = 0
    used_result_count: int = 0
    result_page_index: int = 0
    result_page_count: int = 0
    first_result_index: int = 0
    last_result_index: int = 0
    query_terms: str = ""
    creation_dt: str | None = None
    matches: list[PeppolBusinessCard] = Field(default_factory=list)


def _parse_entity(raw: dict[str, Any]) -> PeppolBusinessEntity:
    names = [
        PeppolDirectoryName(name=n.get("name", ""), language=n.get("language"))
        for n in raw.get("name", [])
    ]
    identifiers = [
        PeppolDirectoryIdentifier(scheme=i.get("scheme", ""), value=i.get("value", ""))
        for i in raw.get("identifiers", [])
    ]
    contacts = [
        PeppolDirectoryContact(
            type=c.get("type"),
            name=c.get("name"),
            phone_number=c.get("phoneNumber"),
            email=c.get("email"),
        )
        for c in raw.get("contacts", [])
    ]
    return PeppolBusinessEntity(
        names=names,
        country_code=raw.get("countryCode"),
        geo_info=raw.get("geoInfo"),
        identifiers=identifiers,
        websites=list(raw.get("websites", [])),
        contacts=contacts,
        additional_info=raw.get("additionalInfo"),
        registration_date=raw.get("regDate"),
    )


def _parse_match(raw: dict[str, Any]) -> PeppolBusinessCard:
    pid_raw = raw.get("participantID", {})
    participant_id = PeppolDirectoryIdentifier(
        scheme=pid_raw.get("scheme", ""), value=pid_raw.get("value", "")
    )
    doc_types = [
        PeppolDirectoryDocType(scheme=d.get("scheme", ""), value=d.get("value", ""))
        for d in raw.get("docTypes", [])
    ]
    entities = [_parse_entity(e) for e in raw.get("entities", [])]
    return PeppolBusinessCard(
        participant_id=participant_id, doc_types=doc_types, entities=entities
    )


def parse_directory_search_response(payload: dict[str, Any]) -> PeppolDirectorySearchResult:
    """Parse a raw ``/search/1.0/json`` response body into a `PeppolDirectorySearchResult`."""
    return PeppolDirectorySearchResult(
        version=payload.get("version", ""),
        total_result_count=payload.get("total-result-count", 0),
        used_result_count=payload.get("used-result-count", 0),
        result_page_index=payload.get("result-page-index", 0),
        result_page_count=payload.get("result-page-count", 0),
        first_result_index=payload.get("first-result-index", 0),
        last_result_index=payload.get("last-result-index", 0),
        query_terms=payload.get("query-terms", ""),
        creation_dt=payload.get("creation-dt"),
        matches=[_parse_match(m) for m in payload.get("matches", [])],
    )


class PeppolDirectoryClient:
    """Client for the public Peppol Directory search REST interface.

    Unauthenticated (no client certificate or OAuth required — search is a
    public service). Instantiate one client per request context or reuse
    across requests; a client-side throttle (~2 q/s) is enforced across
    calls made on the same instance.
    """

    def __init__(
        self,
        environment: PeppolEnvironment = PeppolEnvironment.PRODUCTION,
        http_timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        self._base_url = _BASE_URLS[environment]
        self._http_timeout = http_timeout
        self._max_retries = max_retries
        self._last_request_at: float = 0.0
        self._throttle_lock = asyncio.Lock()

    async def _throttle(self) -> None:
        async with self._throttle_lock:
            now = time.monotonic()
            wait = _MIN_REQUEST_INTERVAL - (now - self._last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = time.monotonic()

    async def search(
        self,
        *,
        q: str | None = None,
        participant: str | None = None,
        name: str | None = None,
        country: str | None = None,
        geoinfo: str | None = None,
        identifier_scheme: str | None = None,
        identifier_value: str | None = None,
        website: str | None = None,
        contact: str | None = None,
        addinfo: str | None = None,
        regdate: str | None = None,
        doctype: str | None = None,
        result_page_index: int = 0,
        result_page_count: int = 20,
        fmt: str = "json",
    ) -> PeppolDirectorySearchResult:
        """Search the Peppol Directory.

        At least one query term must be supplied (``q``, ``participant``,
        ``name``, ``country``, ``geoinfo``, ``identifier_scheme``/
        ``identifier_value``, ``website``, ``contact``, ``addinfo``,
        ``regdate``, or ``doctype``) — the Directory returns HTTP 400
        otherwise (spec section 7.1.2).

        Args:
            q: General purpose query term, matched across all fields.
            participant: Exact match on the participant identifier
                (scheme must be included, e.g. "iso6523-actorid-upis::0208:...").
            name: Partial match on entity name (min. 3 characters).
            country: Exact match (case-insensitive) on ISO 3166-2 country code.
            geoinfo: Partial match on geographic information (min. 3 characters).
            identifier_scheme: Exact match on an additional identifier's type
                (combine with identifier_value).
            identifier_value: Exact match on an additional identifier's value
                (combine with identifier_scheme).
            website: Partial match on website URL (min. 3 characters).
            contact: Partial match on contact fields (min. 3 characters).
            addinfo: Partial match on additional information (min. 3 characters).
            regdate: Exact match on registration date, "YYYY-MM-DD".
            doctype: Exact match (case-sensitive) on a document type identifier
                (identifier scheme must be included).
            result_page_index: 0-based result page index.
            result_page_count: Results per page (Directory returns at most 1000
                total across paging).
            fmt: Response format, "json" or "xml". Only "json" is parsed by
                this client; "xml" is rejected with ValueError.

        Raises:
            ValueError: If no query term is supplied, or fmt is not "json".
            PlatformError: If the Directory returns a non-2xx response after
                retries are exhausted.
        """
        if fmt != "json":
            raise ValueError(
                f"PeppolDirectoryClient only parses fmt='json' responses, got {fmt!r}."
            )

        params: dict[str, str] = {}
        if q is not None:
            params["q"] = q
        if participant is not None:
            params["participant"] = participant
        if name is not None:
            params["name"] = name
        if country is not None:
            params["country"] = country
        if geoinfo is not None:
            params["geoinfo"] = geoinfo
        if identifier_scheme is not None:
            params["identifierScheme"] = identifier_scheme
        if identifier_value is not None:
            params["identifierValue"] = identifier_value
        if website is not None:
            params["website"] = website
        if contact is not None:
            params["contact"] = contact
        if addinfo is not None:
            params["addinfo"] = addinfo
        if regdate is not None:
            params["regdate"] = regdate
        if doctype is not None:
            params["doctype"] = doctype
        if not params:
            raise ValueError(
                "At least one query term (q, participant, name, country, geoinfo, "
                "identifier_scheme/identifier_value, website, contact, addinfo, "
                "regdate, doctype) must be supplied."
            )
        params["resultPageIndex"] = str(result_page_index)
        params["resultPageCount"] = str(result_page_count)

        url = f"{self._base_url}/search/1.0/{fmt}"
        payload = await self._get_json(url, params)
        return parse_directory_search_response(payload)

    async def _get_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        attempt = 0
        last_response: httpx.Response | None = None
        async with httpx.AsyncClient(timeout=self._http_timeout, trust_env=False) as client:
            while attempt <= self._max_retries:
                await self._throttle()
                logger.debug("Peppol Directory search: GET %s params=%s", url, params)
                response = await client.get(url, params=params, headers={"Accept": "application/json"})
                if response.is_success:
                    return response.json()
                if response.status_code in (429, 503) and attempt < self._max_retries:
                    delay = compute_retry_delay(response, attempt)
                    logger.warning(
                        "Peppol Directory search throttled (HTTP %d), retrying in %.1fs",
                        response.status_code,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    attempt += 1
                    last_response = response
                    continue
                last_response = response
                break

        assert last_response is not None  # loop always sets it before break/exhaustion
        raise PlatformError(
            status_code=last_response.status_code,
            message=f"Peppol Directory search failed: HTTP {last_response.status_code}: "
            f"{last_response.text[:300]}",
        )
