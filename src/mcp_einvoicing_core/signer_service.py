"""Standalone signer/submitter microservice for mcp-einvoicing.

Run as a separate OS process before starting the MCP server so that PKCS#12
material and mTLS SSL contexts never enter the LLM-facing FastMCP process.

    python -m mcp_einvoicing_core.signer_service

Environment variables
---------------------
EINVOICING_CERT_PATH        Path to the PKCS#12 (.p12 / .pfx) file.
EINVOICING_CERT_PASSWORD    Passphrase for the file (empty string if none).
EINVOICING_SIGNER_SOCKET    Unix domain socket path.
                            Default: /tmp/einvoicing-signer-<pid>.sock
EINVOICING_SIGNER_TOKEN     Shared secret the MCP server must present with
                            every request. If unset, a random token is
                            generated and printed to stdout so a wrapper
                            script can capture it.

Protocol
--------
Newline-delimited JSON over a Unix domain socket.

Request:  {"token": "<secret>", "method": "<method>", "params": {...}}\n
Response: {"result": {...}}\n   or   {"error": "<message>"}\n

Methods
-------
sign
    params:
        document_b64          Base64-encoded XML bytes to sign.
        algorithm             (optional) "xades" (default) or "cades-bes".
        signature_policy_id   (optional) XAdES-EPES policy URI.
        signature_policy_hash (optional) Base64-SHA256 of policy doc.
        signature_policy_hash_alg (optional)
        claimed_role          (optional)
    result:
        signed_b64  Base64-encoded signed bytes (XML for XAdES, DER for CAdES).

mtls_submit
    params:
        url          Target HTTPS endpoint.
        payload_b64  Base64-encoded request body (use this OR files, not both).
        content_type (optional, default "application/xml"; ignored when files is set)
        files        (optional) List of multipart file dicts:
                       {"name": str, "filename": str, "content_b64": str, "mime": str}
        extra_headers (optional dict)
    result:
        status_code  int
        body_b64     Base64-encoded response body.
        headers      dict of response headers.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import secrets
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_MAX_REQUEST_BYTES = 64 * 1024 * 1024  # 64 MB


class _SignerService:
    def __init__(
        self,
        cert_path: str,
        cert_password: Optional[str],
        token: str,
        socket_path: str,
    ) -> None:
        self._token = token
        self._socket_path = socket_path

        from mcp_einvoicing_core.digital_signature import _load_pkcs12  # noqa: PLC0415
        from mcp_einvoicing_core.http_client import _build_mtls_ssl_context  # noqa: PLC0415

        logger.info("Loading PKCS#12 credentials from %s", cert_path)
        self._cert_info = _load_pkcs12(cert_path, cert_password)
        self._ssl_context = _build_mtls_ssl_context(cert_path, cert_password)
        logger.info("Credentials loaded; cert serial=%s", self._cert_info.serial_number)

    async def start(self) -> None:
        sock_path = Path(self._socket_path)
        sock_path.unlink(missing_ok=True)

        server = await asyncio.start_unix_server(self._handle, path=str(sock_path))
        os.chmod(str(sock_path), 0o600)
        logger.info("Signer service listening on %s", sock_path)

        async with server:
            await server.serve_forever()

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            raw = await reader.readuntil(b"\n")
            if len(raw) > _MAX_REQUEST_BYTES:
                self._send(writer, {"error": "request too large"})
                return

            try:
                request: dict[str, Any] = json.loads(raw.decode())
            except json.JSONDecodeError as exc:
                self._send(writer, {"error": f"invalid JSON: {exc}"})
                return

            if request.get("token") != self._token:
                self._send(writer, {"error": "unauthorized"})
                return

            method = request.get("method", "")
            params: dict[str, Any] = request.get("params", {})

            if method == "sign":
                result = self._do_sign(params)
            elif method == "mtls_submit":
                result = await self._do_mtls_submit(params)
            else:
                result = {"error": f"unknown method: {method!r}"}

            self._send(writer, result)
        except Exception:
            logger.exception("Unhandled error in signer service handler")
            self._send(writer, {"error": "internal signer error"})
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    @staticmethod
    def _send(writer: asyncio.StreamWriter, payload: dict[str, Any]) -> None:
        writer.write(json.dumps(payload).encode() + b"\n")

    def _do_sign(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            document_bytes = base64.b64decode(params["document_b64"])
        except Exception as exc:
            return {"error": f"invalid document_b64: {exc}"}

        algorithm = params.get("algorithm", "xades")

        if algorithm == "cades-bes":
            from mcp_einvoicing_core.digital_signature import (  # noqa: PLC0415
                CAdESSigner,
                CAdESSignerConfig,
            )

            config = CAdESSignerConfig(
                cert_path="",
                cert_password=None,
            )
            signer = CAdESSigner(config, _preloaded_cert_info=self._cert_info)
            label = "CAdES-BES"
        else:
            from mcp_einvoicing_core.digital_signature import (  # noqa: PLC0415
                XAdESEPESSigner,
                XAdESSignerConfig,
            )

            config = XAdESSignerConfig(
                cert_path="",
                cert_password=None,
                signature_policy_id=params.get("signature_policy_id"),
                signature_policy_hash=params.get("signature_policy_hash"),
                signature_policy_hash_alg=params.get(
                    "signature_policy_hash_alg",
                    "http://www.w3.org/2001/04/xmlenc#sha256",
                ),
                claimed_role=params.get("claimed_role"),
            )
            signer = XAdESEPESSigner(config, _preloaded_cert_info=self._cert_info)
            label = "XAdES-EPES"

        try:
            signed_bytes = signer.sign(document_bytes)
        except Exception as exc:
            logger.exception("%s signing failed", label)
            return {"error": f"signing failed: {exc}"}

        return {"result": {"signed_b64": base64.b64encode(signed_bytes).decode()}}

    async def _do_mtls_submit(self, params: dict[str, Any]) -> dict[str, Any]:
        import httpx  # noqa: PLC0415

        url = params.get("url", "")
        if not url:
            return {"error": "url is required"}

        extra_headers: dict[str, str] = params.get("extra_headers", {})
        raw_files: list[dict[str, Any]] = params.get("files", [])

        try:
            async with httpx.AsyncClient(
                verify=self._ssl_context, timeout=60.0
            ) as client:
                if raw_files:
                    files = [
                        (
                            f["name"],
                            (f["filename"], base64.b64decode(f["content_b64"]), f["mime"]),
                        )
                        for f in raw_files
                    ]
                    response = await client.post(url, files=files, headers=extra_headers)
                else:
                    payload = base64.b64decode(params.get("payload_b64", ""))
                    content_type = params.get("content_type", "application/xml")
                    headers = {"Content-Type": content_type, **extra_headers}
                    response = await client.post(url, content=payload, headers=headers)
        except Exception as exc:
            logger.exception("mTLS submit failed for %s", url)
            return {"error": f"submission failed: {exc}"}

        return {
            "result": {
                "status_code": response.status_code,
                "body_b64": base64.b64encode(response.content).decode(),
                "headers": dict(response.headers),
            }
        }


def _default_socket_path() -> str:
    return os.path.join(tempfile.gettempdir(), f"einvoicing-signer-{os.getpid()}.sock")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [signer] %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    cert_path = os.environ.get("EINVOICING_CERT_PATH", "")
    if not cert_path:
        sys.exit("EINVOICING_CERT_PATH is required")

    cert_password: Optional[str] = os.environ.get("EINVOICING_CERT_PASSWORD") or None
    socket_path = os.environ.get("EINVOICING_SIGNER_SOCKET") or _default_socket_path()
    token = os.environ.get("EINVOICING_SIGNER_TOKEN") or secrets.token_hex(32)

    # Wipe credential env vars from this process before any tool can read them.
    os.environ.pop("EINVOICING_CERT_PATH", None)
    os.environ.pop("EINVOICING_CERT_PASSWORD", None)

    print(f"EINVOICING_SIGNER_SOCKET={socket_path}", flush=True)
    print(f"EINVOICING_SIGNER_TOKEN={token}", flush=True)

    service = _SignerService(cert_path, cert_password, token, socket_path)
    asyncio.run(service.start())


if __name__ == "__main__":
    main()
