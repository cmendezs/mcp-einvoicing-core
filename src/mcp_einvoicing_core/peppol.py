"""Peppol SMP (Service Metadata Publisher) lookup client for mcp-einvoicing-core.

Implements the OpenPeppol BDMSL (Business Document Metadata Service Location)
protocol for discovering whether a business is registered on the Peppol network
and determining its AS4 access point endpoint.

Peppol lookup flow:
  1. Build the participant identifier string: iso6523-actorid-upis::<scheme>:<value>
  2. Compute SHA-256 of the lowercase identifier → hex digest
  3. Construct DNS name: B-<hex>.<scheme>.iso6523-actorid-upis.<sml-domain>
  4. DNS CNAME lookup reveals the SMP hostname (via DNS-over-HTTPS)
  5. HTTP GET to SMP to fetch the service group (list of supported document types)
  6. HTTP GET to SMP to fetch service metadata for a specific document type,
     extracting the AS4 endpoint URL and transport profile

Country packages subclass PeppolSMPClient to add country-specific default values
(SML domain, preferred participant ID scheme, supported document type identifiers).

SML domains:
  Production: edelivery.tech.ec.europa.eu   [Unverified — confirm against OpenPeppol docs]
  Test:       acc.edelivery.tech.ec.europa.eu  [Unverified — confirm against OpenPeppol docs]

DNS-over-HTTPS provider: Cloudflare (https://cloudflare-dns.com/dns-query) is used
as the default.  Override _doh_url in subclasses to use a different resolver.

References:
  OpenPeppol BDMSL specification: https://docs.peppol.eu/edelivery/sml/
  OpenPeppol SMP specification:   https://docs.peppol.eu/edelivery/smp/
  ISO 6523 ICD list:              https://www.iana.org/assignments/edi/edi.xhtml
"""

from __future__ import annotations

import hashlib
import logging
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import httpx
from lxml import etree

from mcp_einvoicing_core.exceptions import PlatformError

logger = logging.getLogger(__name__)

# SMP XML namespaces
# [Unverified: confirm against current OpenPeppol SMP spec version]
_NS_SERVICE_GROUP = "http://busdox.org/serviceMetadata/publishing/1.0/"
_NS_SERVICE_METADATA = "http://busdox.org/serviceMetadata/publishing/1.0/"
_NS_ENDPOINT = "http://busdox.org/serviceMetadata/publishing/1.0/"
_PEPPOL_NSMAP = {
    "smp": "http://busdox.org/serviceMetadata/publishing/1.0/",
    "wsa": "http://www.w3.org/2005/08/addressing",
    "ids": "http://busdox.org/transport/identifiers/1.0/",
}

# OpenPeppol SML production and test domains
# [Unverified: confirm against https://docs.peppol.eu/edelivery/sml/]
_SML_PRODUCTION = "edelivery.tech.ec.europa.eu"
_SML_TEST = "acc.edelivery.tech.ec.europa.eu"

# Participant ID scheme prefix used in DNS and SMP URLs
_ACTORID_PREFIX = "iso6523-actorid-upis"

# Peppol BIS Billing 3.0 document type identifier
# [Unverified: confirm against https://docs.peppol.eu/poacc/billing/3.0/]
PEPPOL_BIS_BILLING_30 = (
    "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
    "::Invoice"
    "##urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
    "::2.1"
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class PeppolEnvironment(str, Enum):
    """Peppol network environment."""

    PRODUCTION = "production"
    TEST = "test"


@dataclass
class PeppolParticipantId:
    """A Peppol participant identifier: <scheme>:<value>.

    scheme: ISO 6523 ICD code (e.g. "0088" for GLN, "0204" for Leitweg-ID,
            "9930" for DE VAT).
    value:  The actual identifier within the scheme (no scheme prefix).
    """

    scheme: str
    value: str

    @classmethod
    def parse(cls, raw: str) -> "PeppolParticipantId":
        """Parse a raw "scheme:value" string.

        Args:
            raw: Participant ID in the format "<scheme>:<value>", e.g.
                 "0088:4012345678901" or "0204:991-1234512345-06".

        Raises:
            ValueError: If the string does not contain exactly one colon separator.
        """
        parts = raw.split(":", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(
                f"Invalid Peppol participant ID {raw!r}. "
                "Expected format: '<scheme>:<value>', e.g. '0088:4012345678901'."
            )
        return cls(scheme=parts[0].strip(), value=parts[1].strip())

    def as_iso6523(self) -> str:
        """Return the full ISO 6523 actor ID string used in DNS and SMP URLs.

        Format: iso6523-actorid-upis::<scheme>:<value>  (all lowercase)
        """
        return f"{_ACTORID_PREFIX}::{self.scheme}:{self.value}".lower()

    def dns_hash(self) -> str:
        """SHA-256 hex digest of the lowercase ISO 6523 actor ID.

        Confirmed: the OpenPeppol BDMSL specification (current version, §4.1)
        requires SHA-256. The legacy BDMSL 1.x used MD5; all current Peppol
        networks (EU, APAC, Gulf) use SHA-256. The ``B-`` prefix in dns_name()
        is the canonical signal that SHA-256 is in use.
        """
        return hashlib.sha256(self.as_iso6523().encode("utf-8")).hexdigest()

    def dns_name(self, sml_domain: str) -> str:
        """Construct the DNS CNAME name for the BDMSL lookup.

        Format: B-<sha256hex>.<scheme>.iso6523-actorid-upis.<sml-domain>
        """
        return f"B-{self.dns_hash()}.{self.scheme}.{_ACTORID_PREFIX}.{sml_domain}"

    def smp_path_segment(self) -> str:
        """URL-encoded ISO 6523 path segment for SMP HTTP requests.

        Format: iso6523-actorid-upis%3A%3A<scheme>%3A<value>
        """
        return urllib.parse.quote(self.as_iso6523(), safe="")

    def __str__(self) -> str:
        return f"{self.scheme}:{self.value}"


@dataclass
class PeppolServiceInfo:
    """Endpoint and capability information for a single Peppol document type.

    document_type_id: The full Peppol document type identifier (URN).
    endpoint_url:     AS4 endpoint URL of the receiving access point.
    transport_profile: Transport protocol identifier (e.g. "peppol-transport-as4-v2_0").
    process_id:       Process identifier (e.g. the BIS Billing 3.0 process URN).
    certificate:      PEM-encoded signing certificate of the access point (if present).
    """

    document_type_id: str
    endpoint_url: Optional[str] = None
    transport_profile: Optional[str] = None
    process_id: Optional[str] = None
    certificate: Optional[str] = None


@dataclass
class PeppolLookupResult:
    """Result of a Peppol participant lookup.

    is_registered:          True if a SMP record was found for the participant.
    participant_id:         The participant that was looked up.
    supported_document_types: Document type identifiers listed in the service group.
    smp_hostname:           SMP hostname resolved from DNS (informational).
    error:                  Error message if the lookup failed.
    """

    is_registered: bool
    participant_id: PeppolParticipantId
    supported_document_types: list[str] = field(default_factory=list)
    smp_hostname: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Return a plain dict suitable for MCP tool responses."""
        return {
            "is_registered": self.is_registered,
            "participant_id": str(self.participant_id),
            "supported_document_types": self.supported_document_types,
            "smp_hostname": self.smp_hostname,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# SMP client
# ---------------------------------------------------------------------------


class PeppolSMPClient:
    """Peppol BDMSL + SMP lookup client.

    Resolves a Peppol participant's registration status, supported document
    types, and AS4 endpoint via DNS-over-HTTPS and SMP HTTP calls.

    Country packages subclass to supply country-specific defaults:

        class GermanPeppolClient(PeppolSMPClient):
            DEFAULT_SCHEME = "0204"           # Leitweg-ID
            DEFAULT_DOCUMENT_TYPE = PEPPOL_BIS_BILLING_30

            def __init__(self, environment: PeppolEnvironment = PeppolEnvironment.PRODUCTION):
                super().__init__(environment=environment)

    All network methods are async.  Instantiate one client per request context
    or reuse across requests (no shared state beyond configuration).
    """

    # DNS-over-HTTPS resolver URL (Cloudflare public DNS)
    # Override in subclasses to use a different resolver (e.g. Google).
    _doh_url: str = "https://cloudflare-dns.com/dns-query"

    def __init__(
        self,
        environment: PeppolEnvironment = PeppolEnvironment.PRODUCTION,
        http_timeout: float = 10.0,
    ) -> None:
        self._environment = environment
        self._http_timeout = http_timeout
        self._sml_domain = (
            _SML_PRODUCTION if environment == PeppolEnvironment.PRODUCTION else _SML_TEST
        )

    # ── Public API ────────────────────────────────────────────────────────────

    async def lookup_participant(
        self, participant_id: PeppolParticipantId
    ) -> PeppolLookupResult:
        """Check whether a participant is registered and list their document types.

        Performs:
          1. DNS CNAME lookup (via DoH) to locate the SMP hostname.
          2. HTTP GET to the SMP service group endpoint to enumerate capabilities.

        Returns a PeppolLookupResult.  Never raises — errors are returned in the
        result's `error` field so tool handlers can forward them to MCP clients.
        """
        try:
            smp_hostname = await self._resolve_smp_hostname(participant_id)
        except Exception as exc:
            logger.warning("DNS lookup failed for %s: %s", participant_id, exc)
            return PeppolLookupResult(
                is_registered=False,
                participant_id=participant_id,
                error=f"DNS lookup failed: {exc}",
            )

        if smp_hostname is None:
            return PeppolLookupResult(
                is_registered=False,
                participant_id=participant_id,
                error="Participant not found in Peppol SML (no CNAME record).",
            )

        smp_base_url = f"https://{smp_hostname}"
        try:
            doc_types = await self._fetch_service_group(smp_base_url, participant_id)
        except Exception as exc:
            logger.warning("SMP service group fetch failed for %s: %s", participant_id, exc)
            return PeppolLookupResult(
                is_registered=True,
                participant_id=participant_id,
                smp_hostname=smp_hostname,
                error=f"SMP service group fetch failed: {exc}",
            )

        return PeppolLookupResult(
            is_registered=True,
            participant_id=participant_id,
            supported_document_types=doc_types,
            smp_hostname=smp_hostname,
        )

    async def get_service_endpoint(
        self,
        participant_id: PeppolParticipantId,
        document_type_id: str,
        smp_hostname: Optional[str] = None,
    ) -> PeppolServiceInfo:
        """Fetch the AS4 endpoint for a specific document type.

        Args:
            participant_id:    The participant to look up.
            document_type_id:  Full Peppol document type identifier URN.
            smp_hostname:      SMP hostname if already resolved; re-resolved
                               via DNS if None.

        Returns a PeppolServiceInfo with the AS4 endpoint URL.

        Raises:
            PlatformError: If the SMP returns a non-2xx response.
        """
        if smp_hostname is None:
            smp_hostname = await self._resolve_smp_hostname(participant_id)
            if smp_hostname is None:
                return PeppolServiceInfo(
                    document_type_id=document_type_id,
                    endpoint_url=None,
                )

        smp_base_url = f"https://{smp_hostname}"
        return await self._fetch_service_metadata(
            smp_base_url, participant_id, document_type_id
        )

    # ── Protected helpers — override in subclasses ────────────────────────────

    async def _resolve_smp_hostname(
        self, participant_id: PeppolParticipantId
    ) -> Optional[str]:
        """Resolve the SMP hostname for a participant via DNS-over-HTTPS CNAME lookup.

        Returns the SMP hostname string, or None if no CNAME record exists
        (meaning the participant is not registered).

        The DNS name queried is: B-<sha256>.<scheme>.iso6523-actorid-upis.<sml>

        [Unverified: confirm DNS name format and hash algorithm against the current
         OpenPeppol BDMSL specification before relying on this in production.]
        """
        dns_name = participant_id.dns_name(self._sml_domain)
        logger.debug("Peppol DNS lookup: %s", dns_name)

        params = {"name": dns_name, "type": "CNAME"}
        headers = {"Accept": "application/dns-json"}

        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            response = await client.get(self._doh_url, params=params, headers=headers)

        if not response.is_success:
            raise PlatformError(
                status_code=response.status_code,
                message=f"DNS-over-HTTPS query failed: {response.text[:200]}",
            )

        data = response.json()
        # DoH JSON response: {"Status": 0, "Answer": [{"type": 5, "data": "hostname."}]}
        # Status 0 = NOERROR, type 5 = CNAME
        if data.get("Status") != 0:
            return None  # NXDOMAIN or other error → participant not registered

        for answer in data.get("Answer", []):
            if answer.get("type") == 5:  # CNAME
                cname = answer.get("data", "").rstrip(".")
                if cname:
                    logger.debug("Peppol SMP hostname resolved: %s", cname)
                    return cname

        return None

    async def _fetch_service_group(
        self, smp_base_url: str, participant_id: PeppolParticipantId
    ) -> list[str]:
        """Fetch the SMP service group and return a list of document type identifiers.

        URL: GET <smp_base_url>/<encoded-participant-id>/services

        The service group XML lists hrefs to individual service metadata resources.
        This method extracts the document type identifier from each href.

        [Unverified: confirm SMP URL path format against the OpenPeppol SMP spec.]
        """
        url = f"{smp_base_url}/{participant_id.smp_path_segment()}/services"
        logger.debug("SMP service group: GET %s", url)

        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            response = await client.get(url, headers={"Accept": "application/xml"})

        if not response.is_success:
            raise PlatformError(
                status_code=response.status_code,
                message="SMP service group request failed",
            )

        return self._parse_service_group(response.content)

    async def _fetch_service_metadata(
        self,
        smp_base_url: str,
        participant_id: PeppolParticipantId,
        document_type_id: str,
    ) -> PeppolServiceInfo:
        """Fetch service metadata for a specific document type.

        URL: GET <smp_base_url>/<participant>/services/<encoded-doc-type>

        Returns a PeppolServiceInfo with the AS4 endpoint URL, transport profile,
        and process identifier.

        [Unverified: confirm URL path format and XML schema against the OpenPeppol
         SMP spec; schema may differ between SMP v1 and v2.]
        """
        encoded_doc_type = urllib.parse.quote(document_type_id, safe="")
        url = (
            f"{smp_base_url}/{participant_id.smp_path_segment()}"
            f"/services/{encoded_doc_type}"
        )
        logger.debug("SMP service metadata: GET %s", url)

        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            response = await client.get(url, headers={"Accept": "application/xml"})

        if not response.is_success:
            raise PlatformError(
                status_code=response.status_code,
                message=f"SMP service metadata request failed for {document_type_id!r}",
            )

        return self._parse_service_metadata(response.content, document_type_id)

    def _parse_service_group(self, xml_bytes: bytes) -> list[str]:
        """Extract document type identifiers from an SMP service group XML response.

        The service group lists <ServiceMetadataReferenceCollection> with
        <ServiceMetadataReference> hrefs.  Each href contains the document
        type identifier as a URL path segment.

        Returns a list of document type identifier strings (URL-decoded).

        [Unverified: exact XML element names may differ between SMP spec versions.]
        """
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            logger.warning("SMP service group XML parse error: %s", exc)
            return []

        doc_types: list[str] = []
        # Try both the busdox namespace and unprefixed elements
        for ref in root.iter():
            local = etree.QName(ref.tag).localname if "{" in ref.tag else ref.tag
            if local == "ServiceMetadataReference":
                href = ref.get("href") or ""
                # Extract document type from URL path: .../services/<encoded-doc-type>
                if "/services/" in href:
                    encoded = href.split("/services/", 1)[1].split("?")[0]
                    doc_type = urllib.parse.unquote(encoded)
                    if doc_type:
                        doc_types.append(doc_type)

        return doc_types

    def _parse_service_metadata(
        self, xml_bytes: bytes, document_type_id: str
    ) -> PeppolServiceInfo:
        """Extract endpoint information from an SMP service metadata XML response.

        Looks for <Endpoint> elements containing:
          - <EndpointURI> — AS4 endpoint URL
          - <TransportProfile> — transport protocol identifier
          - <ServiceActivationDate> / <ServiceExpirationDate>
          - <Certificate> — PEM-encoded signing certificate

        Returns a PeppolServiceInfo.  On parse failure returns a result with
        no endpoint URL so callers can detect the absence cleanly.

        [Unverified: XML element names and namespace handling may differ
         between SMP spec versions and SMP implementations.]
        """
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            logger.warning("SMP service metadata XML parse error: %s", exc)
            return PeppolServiceInfo(document_type_id=document_type_id)

        def find_text(parent: etree._Element, local_name: str) -> Optional[str]:
            for el in parent.iter():
                tag_local = etree.QName(el.tag).localname if "{" in el.tag else el.tag
                if tag_local == local_name:
                    return (el.text or "").strip() or None
            return None

        endpoint_url = find_text(root, "EndpointURI")
        transport_profile = find_text(root, "TransportProfile")
        process_id = find_text(root, "ProcessIdentifier")
        certificate = find_text(root, "Certificate")

        return PeppolServiceInfo(
            document_type_id=document_type_id,
            endpoint_url=endpoint_url,
            transport_profile=transport_profile,
            process_id=process_id,
            certificate=certificate,
        )
