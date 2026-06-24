"""Sandbox/production URL routing abstraction for country packages.

Provides a common interface so each country package declares its API endpoints
(sandbox and production) in a structured way, and resolves the correct URL at
runtime based on the chosen environment.

Country packages use this by constructing an ``EndpointSet`` per logical API
and grouping them in a ``BaseEnvironmentEndpoints`` container:

    endpoints = BaseEnvironmentEndpoints({
        "submit": EndpointSet(
            sandbox="https://test.example.com/api/submit",
            production="https://api.example.com/api/submit",
        ),
    })
    url = endpoints.get("submit", EndpointEnvironment.SANDBOX)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EndpointEnvironment(str, Enum):
    """Runtime environment selector."""

    SANDBOX = "sandbox"
    PRODUCTION = "production"


class EndpointSet(BaseModel):
    """A pair of sandbox and production URLs for a single logical endpoint."""

    sandbox: Optional[str] = Field(None, description="Sandbox / test environment URL")
    production: Optional[str] = Field(None, description="Production environment URL")

    def resolve(self, env: EndpointEnvironment) -> str:
        """Return the URL for the given environment.

        Raises:
            ValueError: If the requested environment URL is not configured.
        """
        url = self.sandbox if env == EndpointEnvironment.SANDBOX else self.production
        if url is None:
            raise ValueError(
                f"No URL configured for environment {env.value!r} in this endpoint set."
            )
        return url


class BaseEnvironmentEndpoints:
    """Container mapping logical endpoint names to sandbox/production URL pairs.

    Args:
        endpoints: A dict mapping logical names to ``EndpointSet`` instances.
    """

    def __init__(self, endpoints: dict[str, EndpointSet] | None = None) -> None:
        self._endpoints: dict[str, EndpointSet] = dict(endpoints or {})

    def get(self, name: str, env: EndpointEnvironment) -> str:
        """Resolve the URL for the named endpoint in the given environment.

        Raises:
            KeyError: If *name* is not a registered endpoint.
            ValueError: If the requested environment URL is not configured.
        """
        if name not in self._endpoints:
            raise KeyError(
                f"Unknown endpoint {name!r}. "
                f"Registered endpoints: {sorted(self._endpoints)}"
            )
        return self._endpoints[name].resolve(env)

    def register(
        self,
        name: str,
        *,
        sandbox: str | None = None,
        production: str | None = None,
    ) -> None:
        """Register or overwrite an endpoint by name."""
        self._endpoints[name] = EndpointSet(sandbox=sandbox, production=production)

    def names(self) -> list[str]:
        """Return sorted list of registered endpoint names."""
        return sorted(self._endpoints)
