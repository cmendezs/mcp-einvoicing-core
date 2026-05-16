"""Human-in-the-loop (HITL) confirmation gate for state-changing MCP tools.

Every SIGN, SUBMIT, and DELETE tool uses a two-call pattern:

1. **First call** (no ``confirmation_token``):
   The tool builds a human-readable summary and calls ``require_confirmation()``.
   This stores a pending entry keyed by a random token and returns::

       {
           "status": "awaiting_confirmation",
           "token": "<uuid>",
           "action": "<action_name>",
           "summary": "<human-readable description of what will happen>",
           "expires_in_seconds": 300,
       }

   The LLM must surface this to the user and wait for explicit approval.

2. **Second call** (with ``confirmation_token=<token>``):
   The same tool re-receives the original arguments plus the token.
   It calls ``confirm()`` to validate the token and execute the action.
   On success the pending entry is consumed (single-use).

Configuration
-------------
``EINVOICING_DISABLE_HITL``
    Set to ``1`` / ``true`` / ``yes`` to bypass HITL for trusted local
    deployments or integration tests that call tools programmatically.
    **Never disable in production deployments serving external LLMs.**

Token TTL
---------
Tokens expire after ``ConfirmationStore.TOKEN_TTL_SECONDS`` (default 300 s).
Expired tokens are rejected and must be re-issued by repeating the first call.

Usage in a tool handler
-----------------------
    from mcp_einvoicing_core.confirmation import ConfirmationGate

    async def handle_submit_invoice(xml_content: str, confirmation_token: str | None = None):
        gate = ConfirmationGate.get_default()
        if not gate.is_confirmed(confirmation_token):
            return gate.pending_response(
                action="submit_invoice_to_ksef",
                summary=f"Submit FA(3) invoice to KSeF ({len(xml_content)} bytes)",
                token=confirmation_token,
            )
        # token was valid — execute the action
        result = await _do_submit(xml_content)
        gate.consume(confirmation_token)
        return result
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_HITL_DISABLED: bool = os.environ.get("EINVOICING_DISABLE_HITL", "").strip() in {
    "1", "true", "yes",
}


class ConfirmationStore:
    """Thread-safe in-memory store for pending confirmation tokens.

    Tokens are single-use and expire after ``TOKEN_TTL_SECONDS``.
    """

    TOKEN_TTL_SECONDS: int = 300

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # token → {"action": str, "summary": str, "expires_at": float}
        self._pending: dict[str, dict[str, Any]] = {}

    def issue(self, action: str, summary: str) -> str:
        """Issue a new confirmation token for *action* with *summary*.

        Returns the token string (a URL-safe random 32-char hex string).
        """
        token = secrets.token_hex(16)
        with self._lock:
            self._purge_expired()
            self._pending[token] = {
                "action": action,
                "summary": summary,
                "expires_at": time.monotonic() + self.TOKEN_TTL_SECONDS,
            }
        logger.debug("HITL token issued for action %r: %s", action, token[:8] + "…")
        return token

    def is_valid(self, token: str) -> bool:
        """Return True if *token* exists and has not expired."""
        with self._lock:
            entry = self._pending.get(token)
            if entry is None:
                return False
            if time.monotonic() > entry["expires_at"]:
                del self._pending[token]
                return False
            return True

    def consume(self, token: str) -> bool:
        """Remove *token* from the store (single-use enforcement).

        Returns True if the token existed and was removed.
        """
        with self._lock:
            removed = self._pending.pop(token, None)
            return removed is not None

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [t for t, e in self._pending.items() if now > e["expires_at"]]
        for t in expired:
            del self._pending[t]


# ---------------------------------------------------------------------------
# High-level gate API
# ---------------------------------------------------------------------------


class ConfirmationGate:
    """Facade used by tool handlers to implement the two-call HITL pattern.

    If ``EINVOICING_DISABLE_HITL=1`` is set the gate is transparent: every call
    to ``is_confirmed()`` returns ``True`` without requiring a token.

    Use ``ConfirmationGate.get_default()`` to obtain the process-wide singleton.
    Inject a custom instance in tests.
    """

    _default: Optional["ConfirmationGate"] = None
    _default_lock = threading.Lock()

    def __init__(self, store: Optional[ConfirmationStore] = None) -> None:
        self._store = store if store is not None else ConfirmationStore()

    @classmethod
    def get_default(cls) -> "ConfirmationGate":
        """Return the process-wide singleton ``ConfirmationGate``."""
        if cls._default is None:
            with cls._default_lock:
                if cls._default is None:
                    cls._default = cls()
        return cls._default

    def is_confirmed(self, token: Optional[str]) -> bool:
        """Return True if *token* is valid OR if HITL is disabled globally."""
        if _HITL_DISABLED:
            return True
        if token is None:
            return False
        return self._store.is_valid(token)

    def consume(self, token: Optional[str]) -> None:
        """Remove *token* after a confirmed action executes (single-use)."""
        if token is not None and not _HITL_DISABLED:
            self._store.consume(token)

    def pending_response(
        self,
        action: str,
        summary: str,
        token: Optional[str] = None,
    ) -> dict[str, Any]:
        """Return the ``awaiting_confirmation`` dict for the first-call response.

        If *token* is provided and already valid, the same token is re-issued
        (avoids forcing a new token when the user retries the first call).
        Otherwise a fresh token is issued.

        Args:
            action:  Machine-readable action name (e.g. ``"submit_invoice_to_ksef"``).
            summary: Human-readable description shown to the user before they confirm.
            token:   Token from a previous first call, if any.
        """
        if token and self._store.is_valid(token):
            issued_token = token
        else:
            issued_token = self._store.issue(action, summary)

        return {
            "status": "awaiting_confirmation",
            "token": issued_token,
            "action": action,
            "summary": summary,
            "expires_in_seconds": ConfirmationStore.TOKEN_TTL_SECONDS,
            "instructions": (
                "Return this tool call with the same arguments and "
                f"confirmation_token={issued_token!r} to execute."
            ),
        }
