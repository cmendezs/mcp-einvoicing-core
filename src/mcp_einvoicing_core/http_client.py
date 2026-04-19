"""
Shared HTTP client for mcp-einvoicing-core.

Extracted and generalised from mcp-facture-electronique-fr (config.py + clients/*.py).

The FR package uses OAuth2 client_credentials for both FlowClient and DirectoryClient.
IT does not use HTTP at all (local processing only).
Future countries:
  Belgium/Poland (Peppol)     → OAuth2 or API-key against Access Point
  Germany (XRechnung)         → mTLS certificate (AuthMode.MTLS — gap flagged in Step 5)
  Spain (FACeB2B)             → mTLS certificate (same gap)
  Poland (KSeF)               → Bearer token (session-based, not client_credentials)

[DECISION: TokenCache is extracted verbatim from FR config.py. It is generic enough
 (any Bearer token with expires_in) to serve future countries.]

[DECISION: The base client supports OAUTH2_CLIENT_CREDENTIALS and NONE.
 MTLS and API_KEY are placeholders (raise NotImplementedError) — added to make it
 clear where country adapters should plug in, without implementing unvalidated logic.]
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any, Optional

import httpx
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

from mcp_einvoicing_core.exceptions import AuthenticationError, PlatformError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth mode enum
# ---------------------------------------------------------------------------


class AuthMode(str, Enum):
    """Authentication mode for BaseEInvoicingClient."""

    OAUTH2_CLIENT_CREDENTIALS = "oauth2_client_credentials"
    """Machine-to-machine OAuth2 (used by FR FlowClient and DirectoryClient)."""

    BEARER_TOKEN = "bearer_token"
    """Static or session Bearer token (e.g. KSeF Poland session tokens)."""

    NONE = "none"
    """No authentication — local processing or unauthenticated endpoints."""

    MTLS = "mtls"
    """Mutual TLS with client certificate (ES FACeB2B, DE ELSTER, Peppol AS4).
    [GAP: Not yet implemented. Country adapters must subclass BaseEInvoicingClient
     and override _get_httpx_client() to inject the cert/key pair.]"""

    API_KEY = "api_key"
    """API-key authentication (header or query param).
    [GAP: Not yet implemented. Subclass and override _get_headers().]"""


# ---------------------------------------------------------------------------
# OAuth2 configuration (Pydantic-settings, env-var driven)
# ---------------------------------------------------------------------------


class OAuthConfig(BaseSettings):
    """OAuth2 client_credentials configuration.

    Country adapters subclass this to add platform-specific base URLs.
    FR: PAConfig(OAuthConfig) adds pa_base_url_flow and pa_base_url_directory.

    [DECISION: Separate OAuthConfig from BaseEInvoicingConfig so countries that
     use no-auth (IT) can still inherit BaseEInvoicingConfig without OAuth fields.]
    """

    token_url: str = Field(..., description="OAuth2 token endpoint URL")
    client_id: str = Field(..., description="OAuth2 Client ID")
    client_secret: str = Field(..., description="OAuth2 Client Secret")
    scope: Optional[str] = Field(default=None, description="OAuth2 scope (optional)")
    http_timeout: float = Field(default=30.0, description="HTTP request timeout in seconds")

    @field_validator("token_url")
    @classmethod
    def strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


class BaseEInvoicingConfig(BaseSettings):
    """Minimal env-var config shared by all country packages.

    Countries that need no HTTP (IT) inherit this with LOG_LEVEL only.
    Countries that need OAuth2 also inherit OAuthConfig.

    [DECISION: IT currently reads LOG_LEVEL and FATTURA_XSD_PATH directly via os.getenv().
     In the refactored IT adapter these become fields on ItalyConfig(BaseEInvoicingConfig).]
    """

    log_level: str = Field(default="INFO", description="Logging level (DEBUG/INFO/WARNING/ERROR)")
    debug: bool = Field(default=False, description="Enable debug logging (overrides log_level)")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


# ---------------------------------------------------------------------------
# Token cache (extracted verbatim from FR config.py TokenCache)
# ---------------------------------------------------------------------------


class TokenCache:
    """OAuth2 Bearer token cache with expiry management.

    The token is renewed EXPIRY_MARGIN_SECONDS before actual expiry to avoid
    401 rejections during in-flight requests.

    Extracted verbatim from mcp-facture-electronique-fr config.py.
    """

    EXPIRY_MARGIN_SECONDS: int = 30

    def __init__(self) -> None:
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0

    def is_valid(self) -> bool:
        """True if the cached token is still valid (with expiry margin)."""
        return (
            self._access_token is not None
            and time.monotonic() < self._expires_at - self.EXPIRY_MARGIN_SECONDS
        )

    def set(self, access_token: str, expires_in: int) -> None:
        """Store a new token with its validity duration in seconds."""
        self._access_token = access_token
        self._expires_at = time.monotonic() + expires_in
        logger.debug("OAuth2 token renewed, expires in %ds", expires_in)

    def get(self) -> Optional[str]:
        """Return the current valid token, or None if expired/absent."""
        return self._access_token if self.is_valid() else None

    def invalidate(self) -> None:
        """Force renewal on the next call (call after receiving a 401)."""
        self._access_token = None
        self._expires_at = 0.0


# ---------------------------------------------------------------------------
# HTTP error messages (merged from FR flow_client.py + directory_client.py)
# ---------------------------------------------------------------------------

_HTTP_ERROR_MESSAGES: dict[int, str] = {
    400: "Bad request — check the request format or parameters",
    401: "Unauthenticated — invalid or expired token",
    403: "Access denied — insufficient rights on this resource",
    404: "Resource not found — the provided identifier does not exist",
    413: "Request body too large",
    422: "Unprocessable entity — the request data is semantically invalid",
    429: "Too many requests — rate limit exceeded, retry later",
    500: "Internal platform error — contact the service provider",
    503: "Service unavailable — the platform is under maintenance",
}


def _extract_platform_error(response: httpx.Response) -> PlatformError:
    """Parse an HTTP error response into a PlatformError.

    Attempts to extract structured error details from the response body.
    FR uses {errorCode, errorMessage} (XP Z12-013 Error schema).
    Generic fallback: {detail, message, error_description, error}.
    """
    code = response.status_code
    base_msg = _HTTP_ERROR_MESSAGES.get(code, f"HTTP error {code}")

    detail = ""
    error_code: Optional[str] = None
    try:
        body = response.json()
        # FR XP Z12-013 error schema
        detail = body.get("errorMessage") or ""
        error_code = body.get("errorCode") or None
        # Generic REST error schemas
        if not detail:
            detail = (
                body.get("detail")
                or body.get("message")
                or body.get("error_description")
                or body.get("error")
                or ""
            )
    except Exception:
        detail = response.text[:300] if response.text else ""

    message = f"{base_msg}" + (f" — {detail}" if detail else "")
    logger.error("HTTP %d from platform: %s", code, message)
    return PlatformError(status_code=code, message=message, error_code=error_code)


# ---------------------------------------------------------------------------
# Base async HTTP client
# ---------------------------------------------------------------------------


class BaseEInvoicingClient:
    """Async HTTP client for national e-invoicing platforms.

    Extracted and generalised from FR FlowClient + DirectoryClient.
    Both FR clients share identical _request + 401-retry logic — that is the
    pattern captured here.

    Usage in country adapters:
      class FlowClient(BaseEInvoicingClient):
          def __init__(self, config: PAConfig, oauth: OAuthClient) -> None:
              super().__init__(
                  base_url=config.pa_base_url_flow,
                  auth_mode=AuthMode.OAUTH2_CLIENT_CREDENTIALS,
                  oauth_config=config,
                  http_timeout=config.http_timeout,
              )
    """

    def __init__(
        self,
        base_url: str,
        auth_mode: AuthMode = AuthMode.NONE,
        oauth_config: Optional[OAuthConfig] = None,
        token_cache: Optional[TokenCache] = None,
        static_bearer_token: Optional[str] = None,
        http_timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth_mode = auth_mode
        self._oauth_config = oauth_config
        self._token_cache = token_cache if token_cache is not None else TokenCache()
        self._static_token = static_bearer_token
        self._http_timeout = http_timeout

        if auth_mode == AuthMode.OAUTH2_CLIENT_CREDENTIALS and oauth_config is None:
            raise ValueError("oauth_config is required for OAUTH2_CLIENT_CREDENTIALS auth mode")

    async def _fetch_oauth_token(self) -> str:
        """Obtain a new token via client_credentials grant.

        Extracted from FR OAuthClient._fetch_token().
        """
        assert self._oauth_config is not None

        data: dict[str, str] = {
            "grant_type": "client_credentials",
            "client_id": self._oauth_config.client_id,
            "client_secret": self._oauth_config.client_secret,
        }
        if self._oauth_config.scope:
            data["scope"] = self._oauth_config.scope

        try:
            async with httpx.AsyncClient(timeout=self._oauth_config.http_timeout) as client:
                response = await client.post(self._oauth_config.token_url, data=data)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "OAuth2 token retrieval failed: %s %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise AuthenticationError(
                f"OAuth2 token retrieval failed: {exc.response.status_code}"
            ) from exc

        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise AuthenticationError(
                f"Invalid OAuth2 token response — access_token missing: {payload}"
            )

        expires_in = int(payload.get("expires_in", 3600))
        self._token_cache.set(access_token, expires_in)
        return access_token

    async def _get_bearer_token(self) -> str:
        """Return a valid Bearer token (cached or freshly fetched)."""
        if self._auth_mode == AuthMode.OAUTH2_CLIENT_CREDENTIALS:
            cached = self._token_cache.get()
            if cached:
                return cached
            return await self._fetch_oauth_token()

        if self._auth_mode == AuthMode.BEARER_TOKEN:
            if not self._static_token:
                raise AuthenticationError("static_bearer_token is not set")
            return self._static_token

        raise AuthenticationError(f"Auth mode {self._auth_mode} does not use Bearer tokens")

    async def _get_headers(self) -> dict[str, str]:
        """Build request headers according to auth mode."""
        headers: dict[str, str] = {"Accept": "application/json"}

        if self._auth_mode in (
            AuthMode.OAUTH2_CLIENT_CREDENTIALS,
            AuthMode.BEARER_TOKEN,
        ):
            token = await self._get_bearer_token()
            headers["Authorization"] = f"Bearer {token}"

        elif self._auth_mode == AuthMode.MTLS:
            # [GAP: mTLS — subclass and override _get_httpx_client()]
            raise NotImplementedError(
                "MTLS auth requires subclassing BaseEInvoicingClient and overriding "
                "_get_httpx_client() to provide the client certificate."
            )

        elif self._auth_mode == AuthMode.API_KEY:
            # [GAP: API_KEY — subclass and override _get_headers()]
            raise NotImplementedError(
                "API_KEY auth requires subclassing BaseEInvoicingClient and overriding "
                "_get_headers() to inject the key header."
            )

        return headers

    def invalidate_token(self) -> None:
        """Invalidate the cached token. Call after receiving a 401."""
        self._token_cache.invalidate()
        self._static_token = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[Any] = None,
        data: Optional[dict[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
        retry_on_401: bool = True,
    ) -> httpx.Response:
        """Execute an HTTP request with automatic 401 retry.

        The retry-on-401 pattern is extracted verbatim from both FR clients.
        On a 401: invalidate the token cache and retry exactly once.
        """
        url = f"{self._base_url}{path}"
        headers = await self._get_headers()

        # Content-Type is set automatically by httpx for json/multipart
        if json is not None and files is None:
            headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                data=data,
                files=files,
            )

        if response.status_code == 401 and retry_on_401:
            logger.info("Token rejected (401), invalidating and retrying once")
            self.invalidate_token()
            return await self._request(
                method,
                path,
                params=params,
                json=json,
                data=data,
                files=files,
                retry_on_401=False,
            )

        if not response.is_success:
            raise _extract_platform_error(response)

        return response
