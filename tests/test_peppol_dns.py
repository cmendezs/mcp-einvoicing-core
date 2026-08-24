"""Tests for the standalone Peppol U-NAPTR resolver (CORE-PEPPOL-DNS-1).

asyncio_mode = "auto" (pyproject.toml), no @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import pytest

from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.peppol import (
    PeppolEnvironment,
    PeppolParticipantId,
    PeppolSMPClient,
    resolve_naptr,
)

_DNS_NAME = "ABCDEF1234567890.iso6523-actorid-upis.acc.edelivery.tech.ec.europa.eu"


def _doh_json(hostname: str = "test.smp.acube.io") -> dict:
    naptr_data = f'100 0 "U" "Meta:SMP" "!^.*$!https://{hostname}!" .'
    return {"Status": 0, "Answer": [{"type": 35, "data": naptr_data}]}


class TestResolveNaptr:
    async def test_resolves_hostname_from_naptr_record(self, httpx_mock) -> None:
        httpx_mock.add_response(json=_doh_json("test.smp.acube.io"))
        hostname = await resolve_naptr(_DNS_NAME)
        assert hostname == "test.smp.acube.io"

    async def test_returns_none_on_nxdomain(self, httpx_mock) -> None:
        httpx_mock.add_response(json={"Status": 3, "Answer": []})
        hostname = await resolve_naptr(_DNS_NAME)
        assert hostname is None

    async def test_returns_none_when_no_matching_service_record(self, httpx_mock) -> None:
        naptr_data = '100 0 "U" "Meta:OTHER" "!^.*$!https://irrelevant.example!" .'
        httpx_mock.add_response(json={"Status": 0, "Answer": [{"type": 35, "data": naptr_data}]})
        hostname = await resolve_naptr(_DNS_NAME)
        assert hostname is None

    async def test_rejects_hostname_outside_allowlist(self, httpx_mock) -> None:
        httpx_mock.add_response(json=_doh_json("evil.example.com"))
        with pytest.raises(PlatformError):
            await resolve_naptr(_DNS_NAME)

    async def test_raises_platform_error_on_doh_failure(self, httpx_mock) -> None:
        httpx_mock.add_response(status_code=500, text="upstream error")
        with pytest.raises(PlatformError):
            await resolve_naptr(_DNS_NAME)

    async def test_custom_allowlist_check_overrides_default(self, httpx_mock) -> None:
        httpx_mock.add_response(json=_doh_json("custom.internal"))
        hostname = await resolve_naptr(_DNS_NAME, allowlist_check=lambda h: True)
        assert hostname == "custom.internal"

    async def test_respects_custom_service_field(self, httpx_mock) -> None:
        naptr_data = '100 0 "U" "Meta:CUSTOM" "!^.*$!https://test.smp.acube.io!" .'
        httpx_mock.add_response(json={"Status": 0, "Answer": [{"type": 35, "data": naptr_data}]})
        hostname = await resolve_naptr(_DNS_NAME, service="Meta:CUSTOM")
        assert hostname == "test.smp.acube.io"


class TestPeppolSMPClientDelegatesToResolveNaptr:
    """PeppolSMPClient._resolve_smp_hostname must keep behaving identically
    now that it delegates to the standalone resolve_naptr() (no regression
    from the CORE-PEPPOL-DNS-1 promotion)."""

    async def test_resolve_smp_hostname_delegates(self, httpx_mock) -> None:
        httpx_mock.add_response(json=_doh_json("test.smp.acube.io"))
        client = PeppolSMPClient(environment=PeppolEnvironment.TEST)
        participant_id = PeppolParticipantId.parse("0208:0123456789")
        hostname = await client._resolve_smp_hostname(participant_id)
        assert hostname == "test.smp.acube.io"

    async def test_resolve_smp_hostname_still_enforces_allowlist(self, httpx_mock) -> None:
        httpx_mock.add_response(json=_doh_json("evil.example.com"))
        client = PeppolSMPClient(environment=PeppolEnvironment.TEST)
        participant_id = PeppolParticipantId.parse("0208:0123456789")
        with pytest.raises(PlatformError):
            await client._resolve_smp_hostname(participant_id)
