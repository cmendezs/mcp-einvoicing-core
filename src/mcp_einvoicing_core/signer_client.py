"""Client for the mcp-einvoicing signer microservice.

MCP tool handlers import ``SignerClient`` and call ``sign()`` or
``mtls_submit()`` instead of loading PKCS#12 material directly.  The
actual key material lives only in the signer process (started separately
via ``python -m mcp_einvoicing_core.signer_service``).

Configuration (environment variables read at instantiation time):
    EINVOICING_SIGNER_SOCKET   Unix domain socket path of the running service.
    EINVOICING_SIGNER_TOKEN    Capability token printed by the service on startup.

Usage in a tool handler::

    from mcp_einvoicing_core.signer_client import SignerClient

    client = SignerClient.from_env()
    signed_bytes = await client.sign(xml_bytes, signature_policy_id="https://...")
    result = await client.mtls_submit(url, payload_bytes)
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from typing import Any, Optional


class SignerError(Exception):
    """Raised when the signer service returns an error or is unreachable."""


class SignerClient:
    """Async client for the einvoicing signer microservice."""

    def __init__(self, socket_path: str, token: str) -> None:
        self._socket_path = socket_path
        self._token = token

    @classmethod
    def from_env(cls) -> "SignerClient":
        """Build a client from EINVOICING_SIGNER_SOCKET and EINVOICING_SIGNER_TOKEN.

        Raises:
            SignerError: If either environment variable is not set.
        """
        socket_path = os.environ.get("EINVOICING_SIGNER_SOCKET", "")
        token = os.environ.get("EINVOICING_SIGNER_TOKEN", "")
        if not socket_path or not token:
            raise SignerError(
                "EINVOICING_SIGNER_SOCKET and EINVOICING_SIGNER_TOKEN must be set. "
                "Start the signer service first: "
                "python -m mcp_einvoicing_core.signer_service"
            )
        return cls(socket_path=socket_path, token=token)

    @classmethod
    def is_configured(cls) -> bool:
        """Return True if both signer env vars are set (non-empty)."""
        return bool(
            os.environ.get("EINVOICING_SIGNER_SOCKET")
            and os.environ.get("EINVOICING_SIGNER_TOKEN")
        )

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request = json.dumps(
            {"token": self._token, "method": method, "params": params}
        ).encode() + b"\n"

        try:
            reader, writer = await asyncio.open_unix_connection(self._socket_path)
        except (FileNotFoundError, ConnectionRefusedError) as exc:
            raise SignerError(
                f"Cannot connect to signer service at {self._socket_path!r}: {exc}. "
                "Is the signer process running?"
            ) from exc

        try:
            writer.write(request)
            await writer.drain()
            raw = await reader.readline()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

        try:
            response: dict[str, Any] = json.loads(raw.decode())
        except json.JSONDecodeError as exc:
            raise SignerError(f"Signer returned invalid JSON: {exc}") from exc

        if "error" in response:
            raise SignerError(f"Signer error: {response['error']}")

        return response.get("result", {})

    async def sign(
        self,
        document_bytes: bytes,
        *,
        signature_policy_id: Optional[str] = None,
        signature_policy_hash: Optional[str] = None,
        signature_policy_hash_alg: Optional[str] = None,
        claimed_role: Optional[str] = None,
    ) -> bytes:
        """Ask the signer process to apply an XAdES-EPES signature.

        Args:
            document_bytes: Well-formed XML to sign.
            signature_policy_id: XAdES-EPES policy URI (ETSI TS 101 733).
            signature_policy_hash: Base64-SHA256 of the policy document.
            signature_policy_hash_alg: Algorithm URI for the policy hash.
            claimed_role: Optional signer role string.

        Returns:
            Signed XML bytes.

        Raises:
            SignerError: On connection failure or service-reported error.
        """
        params: dict[str, Any] = {
            "document_b64": base64.b64encode(document_bytes).decode(),
        }
        if signature_policy_id:
            params["signature_policy_id"] = signature_policy_id
        if signature_policy_hash:
            params["signature_policy_hash"] = signature_policy_hash
        if signature_policy_hash_alg:
            params["signature_policy_hash_alg"] = signature_policy_hash_alg
        if claimed_role:
            params["claimed_role"] = claimed_role

        result = await self._call("sign", params)

        try:
            return base64.b64decode(result["signed_b64"])
        except Exception as exc:
            raise SignerError(f"Signer returned invalid signed_b64: {exc}") from exc

    async def mtls_submit_files(
        self,
        url: str,
        files: list[tuple[str, str, bytes, str]],
        *,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Ask the signer process to POST a multipart upload via mTLS.

        Args:
            url: Target HTTPS endpoint.
            files: List of ``(field_name, filename, content_bytes, mime_type)`` tuples.
            extra_headers: Additional request headers.

        Returns:
            Same dict as ``mtls_submit``.

        Raises:
            SignerError: On connection failure or service-reported error.
        """
        raw_files = [
            {
                "name": name,
                "filename": filename,
                "content_b64": base64.b64encode(content).decode(),
                "mime": mime,
            }
            for name, filename, content, mime in files
        ]
        params: dict[str, Any] = {
            "url": url,
            "files": raw_files,
            "extra_headers": extra_headers or {},
        }
        result = await self._call("mtls_submit", params)
        body_b64 = result.get("body_b64", "")
        body_bytes = base64.b64decode(body_b64) if body_b64 else b""
        try:
            body_text = body_bytes.decode("utf-8")
        except UnicodeDecodeError:
            body_text = body_bytes.decode("latin-1", errors="replace")
        return {
            "status_code": result.get("status_code", 0),
            "body": body_text,
            "body_b64": body_b64,
            "headers": result.get("headers", {}),
        }

    async def mtls_submit(
        self,
        url: str,
        payload_bytes: bytes,
        *,
        content_type: str = "application/xml",
        extra_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Ask the signer process to POST *payload_bytes* to *url* via mTLS.

        Args:
            url: Target HTTPS endpoint (government gateway).
            payload_bytes: Raw request body.
            content_type: Content-Type header value.
            extra_headers: Additional request headers.

        Returns:
            Dict with ``status_code`` (int), ``body`` (decoded str, best-effort),
            ``body_b64`` (base64), and ``headers`` (dict).

        Raises:
            SignerError: On connection failure or service-reported error.
        """
        params: dict[str, Any] = {
            "url": url,
            "payload_b64": base64.b64encode(payload_bytes).decode(),
            "content_type": content_type,
            "extra_headers": extra_headers or {},
        }
        result = await self._call("mtls_submit", params)

        body_b64 = result.get("body_b64", "")
        body_bytes = base64.b64decode(body_b64) if body_b64 else b""
        try:
            body_text = body_bytes.decode("utf-8")
        except UnicodeDecodeError:
            body_text = body_bytes.decode("latin-1", errors="replace")

        return {
            "status_code": result.get("status_code", 0),
            "body": body_text,
            "body_b64": body_b64,
            "headers": result.get("headers", {}),
        }
