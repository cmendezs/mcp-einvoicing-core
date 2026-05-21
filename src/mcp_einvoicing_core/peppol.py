"""Peppol SMP (Service Metadata Publisher) lookup client for mcp-einvoicing-core.

Implements the OpenPeppol BDMSL (Business Document Metadata Service Location)
protocol for discovering whether a business is registered on the Peppol network
and determining its AS4 access point endpoint.

Peppol lookup flow:
  1. Build the participant identifier string: <scheme>:<value>  (lowercase)
  2. Compute SHA-256 of the lowercase identifier → Base32 digest (RFC 4648, no padding)
  3. Construct DNS name: <base32>.iso6523-actorid-upis.<sml-domain>
  4. DNS U-NAPTR lookup (type 35) reveals the SMP hostname (via DNS-over-HTTPS)
  5. HTTP GET to SMP to fetch the service group (list of supported document types)
  6. HTTP GET to SMP to fetch service metadata for a specific document type,
     extracting the AS4 endpoint URL and transport profile

Country packages subclass PeppolSMPClient to add country-specific default values
(SML domain, preferred participant ID scheme, supported document type identifiers).

SML domains:
  Production: edelivery.tech.ec.europa.eu
  Test:       acc.edelivery.tech.ec.europa.eu

DNS-over-HTTPS provider: Cloudflare (https://cloudflare-dns.com/dns-query) is used
as the default.  Override _doh_url in subclasses to use a different resolver.

References:
  OpenPeppol SMP specification 1.4.0:                https://docs.peppol.eu/edelivery/smp/
  OpenPeppol SML specification 1.3.0:                https://docs.peppol.eu/edelivery/sml/
  OpenPeppol Policy for use of Identifiers 4.4.0:    https://docs.peppol.eu/edelivery/
  ISO 6523 ICD list:                                 https://www.iana.org/assignments/edi/edi.xhtml
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import httpx
from lxml import etree

from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.xml_utils import safe_fromstring

logger = logging.getLogger(__name__)

# SMP XML namespaces (busdox.org — confirmed unchanged in SMP 1.4.0 and SML 1.3.0)
_NS_SERVICE_GROUP = "http://busdox.org/serviceMetadata/publishing/1.0/"
_NS_SERVICE_METADATA = "http://busdox.org/serviceMetadata/publishing/1.0/"
_NS_ENDPOINT = "http://busdox.org/serviceMetadata/publishing/1.0/"
_PEPPOL_NSMAP = {
    "smp": "http://busdox.org/serviceMetadata/publishing/1.0/",
    "wsa": "http://www.w3.org/2005/08/addressing",
    "ids": "http://busdox.org/transport/identifiers/1.0/",
}

# OpenPeppol SML production and test domains (confirmed: SML spec 1.3.0 §2.1)
_SML_PRODUCTION = "edelivery.tech.ec.europa.eu"
_SML_TEST = "acc.edelivery.tech.ec.europa.eu"

# Participant ID meta scheme used in DNS names and SMP URLs (POLICY 5)
_ACTORID_PREFIX = "iso6523-actorid-upis"

# Validation regexes for PeppolParticipantId.parse()
# Scheme: 4-digit ISO 6523 ICD code (POLICY 3, POLICY 6)
# Value: per-scheme character rules; the 128-char cap is a library-level guard
#        (Policy for use of Identifiers 4.4.0 does not state an explicit max length)
_SCHEME_RE = re.compile(r"^[0-9]{4}$")
_VALUE_RE = re.compile(r"^[A-Za-z0-9._:\-]{1,128}$")

# U-NAPTR record (DNS type 35) parsing helpers
# Cloudflare DoH JSON data field format: <order> <pref> "<flags>" "<service>" "<regexp>" <repl>
_NAPTR_DATA_RE = re.compile(
    r'^\d+\s+\d+\s+"(?P<flags>[^"]*)"\s+"(?P<service>[^"]*)"\s+"(?P<regexp>[^"]*)"\s+\S+$'
)
# Peppol U-NAPTR regexp uses ! delimiters: !<pattern>!<uri>!
_NAPTR_URI_RE = re.compile(r"!([^!]*)!([^!]+)!")

# Known Peppol SMP hostname suffixes (P1.11).
# Sources: OpenPeppol AP registry, published SML production participants.
# Override at deployment time via EINVOICING_SMP_ALLOWLIST (comma-separated suffixes).
_SMP_ALLOWLIST_DEFAULT: frozenset[str] = frozenset({
    ".edelivery.tech.ec.europa.eu",   # OpenPeppol SML production
    ".acc.edelivery.tech.ec.europa.eu",  # OpenPeppol SML test
    ".smp.acube.io",
    ".b2brouter.net",
    ".galaxygw.com",
    ".peppolap.com",
    ".einvoiceservice.eu",
    ".openpeppol.org",
    ".digitaldocuments.eu",
})

# Peppol BIS Billing 3.0 document type identifier
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
            ValueError: If the format is invalid, scheme is not a 4-digit ISO 6523
                ICD code, or value contains characters outside [A-Za-z0-9._:-].
        """
        parts = raw.split(":", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(
                f"Invalid Peppol participant ID {raw!r}. "
                "Expected format: '<scheme>:<value>', e.g. '0088:4012345678901'."
            )
        scheme, value = parts[0].strip(), parts[1].strip()
        if not _SCHEME_RE.match(scheme):
            raise ValueError(
                f"Invalid Peppol scheme {scheme!r}: must be exactly 4 decimal digits "
                "(ISO 6523 ICD code, e.g. '0088')."
            )
        if not _VALUE_RE.match(value):
            raise ValueError(
                f"Invalid Peppol participant value {value!r}: must be 1-128 characters "
                "matching [A-Za-z0-9._:-]."
            )
        return cls(scheme=scheme, value=value)

    def as_iso6523(self) -> str:
        """Return the full ISO 6523 actor ID string used in SMP URLs.

        Format: iso6523-actorid-upis::<scheme>:<value>  (all lowercase)
        """
        return f"{_ACTORID_PREFIX}::{self.scheme}:{self.value}".lower()

    def dns_hash(self) -> str:
        """Base32-encoded SHA-256 digest of the lowercased scheme:value identifier.

        Spec: POLICY 7, Peppol Policy for use of Identifiers v4.4.0 (2025-02-06).
        Input:     lowercase "<scheme>:<value>", e.g. "0088:7300010000001"
        Algorithm: SHA-256 of the UTF-8 bytes → Base32 (RFC 4648, no '=' padding)
        """
        identifier = f"{self.scheme}:{self.value}".lower()
        digest = hashlib.sha256(identifier.encode("utf-8")).digest()
        return base64.b32encode(digest).decode("ascii").rstrip("=")

    def dns_name(self, sml_domain: str) -> str:
        """Construct the DNS U-NAPTR name for the SML lookup.

        Format: <base32-hash>.iso6523-actorid-upis.<sml-domain>
        (POLICY 7, Peppol Policy for use of Identifiers v4.4.0)
        """
        return f"{self.dns_hash()}.{_ACTORID_PREFIX}.{sml_domain}"

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
    redirect_url:     SMP redirect target URL (set when the SMP returns a <Redirect>
                      instead of <ServiceInformation>; callers MUST NOT follow more than
                      one hop — SMP 1.4.0 §3.2).
    """

    document_type_id: str
    endpoint_url: Optional[str] = None
    transport_profile: Optional[str] = None
    process_id: Optional[str] = None
    certificate: Optional[str] = None
    redirect_url: Optional[str] = None


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
          1. DNS U-NAPTR lookup (via DoH) to locate the SMP hostname.
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
                error="Participant not found in Peppol SML (no U-NAPTR record).",
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
        """Resolve the SMP hostname for a participant via DNS-over-HTTPS U-NAPTR lookup.

        Returns the SMP hostname string (netloc of the NAPTR URI), or None if no
        U-NAPTR record with service Meta:SMP exists (meaning the participant is not
        registered).

        The DNS name queried is: <base32>.iso6523-actorid-upis.<sml>
        (POLICY 7, Peppol Policy for use of Identifiers v4.4.0)
        Record type: U-NAPTR (DNS type 35, SML specification 1.3.0 §3.2)
        """
        dns_name = participant_id.dns_name(self._sml_domain)
        logger.debug("Peppol DNS lookup: %s", dns_name)

        params = {"name": dns_name, "type": "NAPTR"}
        headers = {"Accept": "application/dns-json"}

        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            response = await client.get(self._doh_url, params=params, headers=headers)

        if not response.is_success:
            raise PlatformError(
                status_code=response.status_code,
                message=f"DNS-over-HTTPS query failed: {response.text[:200]}",
            )

        data = response.json()
        # DoH JSON response: {"Status": 0, "Answer": [{"type": 35, "data": "..."}]}
        # Status 0 = NOERROR, type 35 = NAPTR
        if data.get("Status") != 0:
            return None  # NXDOMAIN or other error → participant not registered

        for answer in data.get("Answer", []):
            if answer.get("type") != 35:  # NAPTR
                continue
            naptr_data = answer.get("data", "")
            m = _NAPTR_DATA_RE.match(naptr_data)
            if not m:
                continue
            if m.group("service").upper() != "META:SMP":
                continue
            uri_m = _NAPTR_URI_RE.search(m.group("regexp"))
            if not uri_m:
                continue
            smp_url = uri_m.group(2)
            parsed = urllib.parse.urlparse(smp_url)
            hostname = parsed.netloc
            if not hostname:
                continue
            if not self._is_allowed_smp_hostname(hostname):
                raise PlatformError(
                    status_code=0,
                    message=(
                        f"Resolved SMP hostname {hostname!r} is not in the Peppol "
                        "AP allowlist. Set EINVOICING_SMP_ALLOWLIST to override."
                    ),
                )
            logger.debug(
                "Peppol SMP hostname resolved: %s (NAPTR URI: %s)", hostname, smp_url
            )
            return hostname

        return None

    def _is_allowed_smp_hostname(self, hostname: str) -> bool:
        """Return True if *hostname* ends with a known Peppol AP suffix.

        The allowlist is seeded from ``_SMP_ALLOWLIST_DEFAULT`` and can be
        extended at deployment time via the ``EINVOICING_SMP_ALLOWLIST``
        environment variable (comma-separated additional suffixes).
        """
        env_extra = os.environ.get("EINVOICING_SMP_ALLOWLIST", "")
        extra: frozenset[str] = (
            frozenset(s.strip() for s in env_extra.split(",") if s.strip())
            if env_extra
            else frozenset()
        )
        allowlist = _SMP_ALLOWLIST_DEFAULT | extra
        hostname_lower = hostname.lower()
        return any(hostname_lower.endswith(suffix) for suffix in allowlist)

    async def _fetch_service_group(
        self, smp_base_url: str, participant_id: PeppolParticipantId
    ) -> list[str]:
        """Fetch the SMP service group and return a list of document type identifiers.

        URL: GET <smp_base_url>/<encoded-participant-id>/services

        The service group XML lists hrefs to individual service metadata resources.
        This method extracts the document type identifier from each href.
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
        and process identifier.  If the SMP returns a <Redirect>, the result's
        redirect_url field is set and endpoint_url is None; callers must not follow
        more than one redirect hop (SMP 1.4.0 §3.2).
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
        """
        try:
            root = safe_fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            logger.warning("SMP service group XML parse error: %s", exc)
            return []

        doc_types: list[str] = []
        for ref in root.iter():
            local = etree.QName(ref.tag).localname if "{" in ref.tag else ref.tag
            if local == "ServiceMetadataReference":
                href = ref.get("href") or ""
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

        Handles both the normal case (<ServiceInformation>) and the redirect case
        (<Redirect>) per SMP specification 1.4.0.

        For <ServiceInformation>, extracts:
          - <wsa:EndpointReference><wsa:Address> — AS4 endpoint URL (SMP 1.4.0)
          - transportProfile XML attribute on <Endpoint> (SMP 1.4.0 / peppol-smp-types-v1.xsd)
          - <ProcessIdentifier> — process identifier
          - <Certificate> — PEM-encoded signing certificate

        For <Redirect>, sets redirect_url and leaves endpoint_url as None.
        Callers must not follow more than one redirect hop (SMP 1.4.0 §3.2).

        Returns a PeppolServiceInfo.  On parse failure returns a result with
        no endpoint URL so callers can detect the absence cleanly.
        """
        try:
            root = safe_fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            logger.warning("SMP service metadata XML parse error: %s", exc)
            return PeppolServiceInfo(document_type_id=document_type_id)

        def find_text(parent: etree._Element, local_name: str) -> Optional[str]:
            for el in parent.iter():
                tag_local = etree.QName(el.tag).localname if "{" in el.tag else el.tag
                if tag_local == local_name:
                    return (el.text or "").strip() or None
            return None

        # Detect <Redirect> — the SMP is delegating this document type to another SMP
        for el in root.iter():
            local = etree.QName(el.tag).localname if "{" in el.tag else el.tag
            if local == "Redirect":
                redirect_url = el.get("href") or None
                logger.debug(
                    "SMP returned Redirect for %s: %s", document_type_id, redirect_url
                )
                return PeppolServiceInfo(
                    document_type_id=document_type_id,
                    redirect_url=redirect_url,
                )

        # Normal <ServiceInformation> path
        endpoint_url: Optional[str] = None
        transport_profile: Optional[str] = None

        for el in root.iter():
            local = etree.QName(el.tag).localname if "{" in el.tag else el.tag
            if local == "Endpoint":
                # transportProfile is an XML attribute on <Endpoint> (SMP 1.4.0 §3.3 /
                # peppol-smp-types-v1.xsd EndpointType)
                transport_profile = el.get("transportProfile") or None
            elif local == "Address":
                # Endpoint URL lives in wsa:EndpointReference/wsa:Address (SMP 1.4.0 §3.3)
                endpoint_url = (el.text or "").strip() or None

        process_id = find_text(root, "ProcessIdentifier")
        certificate = find_text(root, "Certificate")

        return PeppolServiceInfo(
            document_type_id=document_type_id,
            endpoint_url=endpoint_url,
            transport_profile=transport_profile,
            process_id=process_id,
            certificate=certificate,
        )
