"""
Shared HTTP client for mcp-einvoicing-core.

Extracted and generalised from mcp-facture-electronique-fr (config.py + clients/*.py).

The FR package uses OAuth2 client_credentials for both FlowClient and DirectoryClient.
IT does not use HTTP at all (local processing only).
Future countries:
  Belgium/Poland (Peppol)     → OAuth2 or API-key against Access Point
  Germany (XRechnung)         → mTLS certificate (AuthMode.MTLS)
  Spain (FACeB2B / AEAT)      → mTLS certificate (same)
  Poland (KSeF)               → Bearer token (session-based, not client_credentials)

[DECISION: TokenCache is extracted verbatim from FR config.py. It is generic enough
 (any Bearer token with expires_in) to serve future countries.]

[DECISION: The base client supports OAUTH2_CLIENT_CREDENTIALS, NONE, BEARER_TOKEN,
 and MTLS. API_KEY remains a placeholder (raise NotImplementedError) — subclass and
 override _get_headers() when a country needs it.]
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import tempfile
import time
from email.utils import parsedate_to_datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings

from mcp_einvoicing_core.exceptions import AuthenticationError, PlatformError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PKCS#12 / mTLS helpers
# ---------------------------------------------------------------------------


def _build_mtls_ssl_context(cert_path: str, cert_password: Optional[str]) -> ssl.SSLContext:
    """Return an SSLContext loaded with the client certificate from a PKCS#12 file.

    The certificate and private key are extracted in memory using the
    ``cryptography`` library, written to a short-lived temporary file with
    restricted permissions, and immediately deleted after ``load_cert_chain``
    reads them.  The temp-file pattern is required because CPython's
    ``ssl.SSLContext.load_cert_chain`` only accepts file paths or PEM bytes
    (not in-memory key objects).

    Args:
        cert_path: Path to the PKCS#12 (.p12 / .pfx) file.
        cert_password: Passphrase for the file, or ``None`` if unprotected.

    Returns:
        An ``ssl.SSLContext`` configured for mutual TLS client authentication.

    Raises:
        ImportError: If ``cryptography`` is not installed.
        ValueError: If the PKCS#12 file has no certificate or private key.
        FileNotFoundError: If *cert_path* does not exist.
    """
    try:
        from cryptography.hazmat.primitives import serialization  # noqa: PLC0415
        from cryptography.hazmat.primitives.serialization.pkcs12 import (  # noqa: PLC0415
            load_pkcs12,
        )
    except ImportError as exc:
        raise ImportError(
            "cryptography>=42.0.0 is required for MTLS. "
            "Install it: pip install 'cryptography>=42.0.0'"
        ) from exc

    raw = Path(cert_path).read_bytes()
    password = cert_password.encode() if cert_password else None
    p12 = load_pkcs12(raw, password)

    if p12.cert is None:
        raise ValueError(f"No certificate found in PKCS#12 file: {cert_path}")
    if p12.key is None:
        raise ValueError(f"No private key found in PKCS#12 file: {cert_path}")

    cert_pem = p12.cert.certificate.public_bytes(serialization.Encoding.PEM)
    key_pem = p12.key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # Write cert+key to a restricted tempfile, load, then delete immediately.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as tmp:
        tmp_path = tmp.name
        tmp.write(cert_pem + key_pem)

    try:
        ctx.load_cert_chain(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return ctx


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
    """Mutual TLS with client certificate (ES FACeB2B / AEAT, DE ELSTER, Peppol AS4).

    Pass ``cert_path`` and optionally ``cert_password`` to ``BaseEInvoicingClient``
    to activate. The PKCS#12 file is loaded once and reused for all requests.
    """

    API_KEY = "api_key"
    """API-key authentication (header or query param).
    [GAP: Not yet implemented. Subclass and override _get_headers().]"""


# ---------------------------------------------------------------------------
# OAuth2 configuration (Pydantic-settings, env-var driven)
# ---------------------------------------------------------------------------


class OAuthValues(BaseModel):
    """Plain value object for OAuth2 credentials — no environment variable loading.

    Use this when constructing credentials programmatically (multi-country in-process
    deployments, secrets managers, test fixtures). BaseEInvoicingClient accepts
    OAuthValues directly so callers are not forced to bind to .env.

    For env-var / .env loading, use OAuthConfig (which extends this class).
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


class OAuthConfig(OAuthValues, BaseSettings):
    """OAuth2 client_credentials configuration loaded from environment variables.

    Country adapters subclass this to add platform-specific base URLs.
    FR: PAConfig(OAuthConfig) adds pa_base_url_flow and pa_base_url_directory.

    Inherits all fields from OAuthValues. The BaseSettings layer reads them from
    environment variables or a .env file. Pass an OAuthValues instance instead
    when you want to supply credentials without touching the process environment.
    """

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


def _extract_platform_error(
    response: httpx.Response,
    detail: str = "",
    error_code: Optional[str] = None,
) -> PlatformError:
    """Build a PlatformError from a failed HTTP response and pre-parsed detail.

    Body parsing is handled by BaseEInvoicingClient._parse_error_body() so that
    platform-specific schemas (XP Z12-013, KSeF, GSTN, SEFAZ …) can be handled
    by subclass overrides rather than growing this shared function.
    """
    code = response.status_code
    base_msg = _HTTP_ERROR_MESSAGES.get(code, f"HTTP error {code}")
    message = base_msg + (f" — {detail}" if detail else "")
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
        oauth_config: Optional[OAuthValues] = None,
        token_cache: Optional[TokenCache] = None,
        static_bearer_token: Optional[str] = None,
        http_timeout: float = 30.0,
        cert_path: Optional[str] = None,
        cert_password: Optional[str] = None,
        max_retries: int = 3,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth_mode = auth_mode
        self._oauth_config = oauth_config
        self._token_cache = token_cache if token_cache is not None else TokenCache()
        self._static_token = static_bearer_token
        self._http_timeout = http_timeout
        self._cert_path = cert_path
        self._cert_password = cert_password
        self._max_retries = max_retries
        self._mtls_ssl_context: Optional[ssl.SSLContext] = None
        self._client: Optional[httpx.AsyncClient] = None  # long-lived; built on first use

        if auth_mode == AuthMode.OAUTH2_CLIENT_CREDENTIALS and oauth_config is None:
            raise ValueError("oauth_config is required for OAUTH2_CLIENT_CREDENTIALS auth mode")
        if auth_mode == AuthMode.MTLS and cert_path is None:
            raise ValueError("cert_path is required for MTLS auth mode")

    def _get_httpx_client(self) -> httpx.AsyncClient:
        """Build and return a new ``httpx.AsyncClient`` for the active auth mode.

        Called once by ``_get_client()`` to initialise the long-lived client.
        The SSL context for MTLS is built here and cached on the instance.

        Override in a subclass to inject a custom transport (e.g. ``respx``
        mock), a non-default trust store, or per-environment cert rotation.
        The returned client is kept alive for the lifetime of this instance —
        do not close it inside this method.
        """
        if self._auth_mode == AuthMode.MTLS:
            if self._mtls_ssl_context is None:
                assert self._cert_path is not None
                self._mtls_ssl_context = _build_mtls_ssl_context(
                    self._cert_path, self._cert_password
                )
            return httpx.AsyncClient(
                timeout=self._http_timeout, verify=self._mtls_ssl_context
            )
        return httpx.AsyncClient(timeout=self._http_timeout)

    async def _get_client(self) -> httpx.AsyncClient:
        """Return the long-lived ``AsyncClient``, building it on first call.

        Rebuilds automatically if the client has been closed (e.g. after
        ``aclose()`` followed by reuse).
        """
        if self._client is None or self._client.is_closed:
            self._client = self._get_httpx_client()
        return self._client

    async def aclose(self) -> None:
        """Close the underlying ``AsyncClient`` and release all connections.

        Call this when the client instance will no longer be used.
        After calling ``aclose()``, the next ``_request()`` call will rebuild
        the client automatically, so the instance may be reused if needed.
        """
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def __aenter__(self) -> "BaseEInvoicingClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

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
            # The client certificate (loaded in _get_httpx_client) is the
            # authentication mechanism; no Authorization header is needed.
            pass

        elif self._auth_mode == AuthMode.API_KEY:
            # [GAP: API_KEY — subclass and override _get_headers()]
            raise NotImplementedError(
                "API_KEY auth requires subclassing BaseEInvoicingClient and overriding "
                "_get_headers() to inject the key header."
            )

        return headers

    def _parse_error_body(self, response: httpx.Response) -> tuple[str, Optional[str]]:
        """Extract (detail, error_code) from a failed response body.

        Override in a subclass to handle platform-specific error schemas:

            class FRFlowClient(BaseEInvoicingClient):
                def _parse_error_body(self, response):
                    try:
                        body = response.json()
                        # XP Z12-013 error schema
                        return body.get("errorMessage") or "", body.get("errorCode")
                    except Exception:
                        return super()._parse_error_body(response)

        The base implementation handles generic REST schemas:
        {detail}, {message}, {error_description}, {error}.
        """
        try:
            body = response.json()
            detail: str = (
                body.get("detail")
                or body.get("message")
                or body.get("error_description")
                or body.get("error")
                or ""
            )
            return detail, None
        except Exception:
            return (response.text[:300] if response.text else ""), None

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        """Compute seconds to wait before the next retry attempt.

        Parses the ``Retry-After`` header when present (both integer-seconds
        and HTTP-date forms). Falls back to exponential backoff: 1s, 2s, 4s
        … capped at 60s.
        """
        header = response.headers.get("Retry-After", "").strip()
        if header:
            try:
                return max(0.0, float(header))
            except ValueError:
                pass
            try:
                from datetime import datetime, timezone  # noqa: PLC0415

                dt = parsedate_to_datetime(header)
                return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())
            except Exception:
                pass
        return min(1.0 * (2**attempt), 60.0)

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
        """Execute an HTTP request with automatic 401 retry and backoff for 429/503.

        - 401: invalidates the token cache and retries exactly once.
        - 429 / 503: retries up to self._max_retries times, sleeping according
          to _retry_delay() (Retry-After header or exponential backoff).
        - Error body parsing is delegated to _parse_error_body(), which
          subclasses can override for platform-specific error schemas.
        """
        url = f"{self._base_url}{path}"
        client = await self._get_client()

        for attempt in range(self._max_retries + 1):
            headers = await self._get_headers()
            # Content-Type is set automatically by httpx for json/multipart
            if json is not None and files is None:
                headers["Content-Type"] = "application/json"

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

            if response.status_code in (429, 503) and attempt < self._max_retries:
                delay = self._retry_delay(response, attempt)
                logger.warning(
                    "HTTP %d — retrying in %.1fs (attempt %d/%d)",
                    response.status_code,
                    delay,
                    attempt + 1,
                    self._max_retries,
                )
                await asyncio.sleep(delay)
                continue

            if not response.is_success:
                detail, error_code = self._parse_error_body(response)
                raise _extract_platform_error(response, detail, error_code)

            return response

        # Unreachable: the loop always returns or raises, but satisfies type checkers.
        detail, error_code = self._parse_error_body(response)  # type: ignore[possibly-undefined]
        raise _extract_platform_error(response, detail, error_code)  # type: ignore[possibly-undefined]
