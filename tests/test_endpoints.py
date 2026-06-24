"""Tests for BaseEnvironmentEndpoints, EndpointSet, EndpointEnvironment."""

import pytest

from mcp_einvoicing_core.endpoints import (
    BaseEnvironmentEndpoints,
    EndpointEnvironment,
    EndpointSet,
)


class TestEndpointSet:
    def test_resolve_sandbox(self) -> None:
        es = EndpointSet(sandbox="https://test.example.com", production="https://example.com")
        assert es.resolve(EndpointEnvironment.SANDBOX) == "https://test.example.com"

    def test_resolve_production(self) -> None:
        es = EndpointSet(sandbox="https://test.example.com", production="https://example.com")
        assert es.resolve(EndpointEnvironment.PRODUCTION) == "https://example.com"

    def test_resolve_missing_sandbox_raises(self) -> None:
        es = EndpointSet(production="https://example.com")
        with pytest.raises(ValueError, match="sandbox"):
            es.resolve(EndpointEnvironment.SANDBOX)

    def test_resolve_missing_production_raises(self) -> None:
        es = EndpointSet(sandbox="https://test.example.com")
        with pytest.raises(ValueError, match="production"):
            es.resolve(EndpointEnvironment.PRODUCTION)


class TestBaseEnvironmentEndpoints:
    def test_get_registered_endpoint(self) -> None:
        endpoints = BaseEnvironmentEndpoints({
            "submit": EndpointSet(sandbox="https://s.test", production="https://s.prod"),
        })
        assert endpoints.get("submit", EndpointEnvironment.SANDBOX) == "https://s.test"

    def test_get_unknown_endpoint_raises(self) -> None:
        endpoints = BaseEnvironmentEndpoints({})
        with pytest.raises(KeyError, match="unknown"):
            endpoints.get("unknown", EndpointEnvironment.SANDBOX)

    def test_register_and_get(self) -> None:
        endpoints = BaseEnvironmentEndpoints()
        endpoints.register("api", sandbox="https://api.test", production="https://api.prod")
        assert endpoints.get("api", EndpointEnvironment.PRODUCTION) == "https://api.prod"

    def test_names(self) -> None:
        endpoints = BaseEnvironmentEndpoints({
            "b": EndpointSet(),
            "a": EndpointSet(),
        })
        assert endpoints.names() == ["a", "b"]

    def test_register_overwrites(self) -> None:
        endpoints = BaseEnvironmentEndpoints({
            "api": EndpointSet(sandbox="https://old.test"),
        })
        endpoints.register("api", sandbox="https://new.test")
        assert endpoints.get("api", EndpointEnvironment.SANDBOX) == "https://new.test"
