"""Append-only tamper-evident audit log for mcp-einvoicing-core.

Every SIGN, SUBMIT, and CANCEL action is recorded as a JSONL entry.  Each
entry carries a SHA-256 hash of the previous entry (or a genesis sentinel for
the first event), forming a hash chain that makes undetected deletion or
modification of past events computationally infeasible.

Configuration
-------------
``EINVOICING_AUDIT_LOG``
    Absolute path to the JSONL log file.  Parent directory must exist.
    Defaults to ``None`` (log to stderr with a warning) for backward compat.

``EINVOICING_AUDIT_TENANT``
    Optional tenant identifier included in every event.  Useful in
    multi-tenant deployments to partition log entries without separate files.

Thread safety
-------------
``AuditLog.emit()`` acquires a per-instance ``threading.Lock`` before writing.
All appends are atomic at the OS level (O_APPEND on POSIX; each write is a
single ``json.dumps`` line that fits within PIPE_BUF on all supported systems).

Usage
-----
    from mcp_einvoicing_core.audit_log import AuditLog, AuditAction

    log = AuditLog.from_env()            # reads EINVOICING_AUDIT_LOG
    log.emit(
        action=AuditAction.SUBMIT,
        document_ref="INV-2026-001",
        content_sha256="abc123...",
        correlation_id="ksef-ref-xyz",
    )
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# SHA-256 of the empty string — used as the ``prev_hash`` of the first event.
_GENESIS_HASH = hashlib.sha256(b"").hexdigest()


class AuditAction(str, Enum):
    """Actions that must be logged in the tamper-evident audit trail."""

    SIGN = "SIGN"
    SUBMIT = "SUBMIT"
    CANCEL = "CANCEL"


def _sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AuditLog:
    """Append-only, hash-chained JSONL audit log.

    Args:
        log_path: Absolute path to the JSONL file, or ``None`` to write to
                  stderr (development / fallback mode).
        tenant:   Optional tenant identifier injected into every event.
    """

    def __init__(
        self,
        log_path: Optional[str] = None,
        tenant: Optional[str] = None,
    ) -> None:
        self._log_path = log_path
        self._tenant = tenant
        self._lock = threading.Lock()
        self._prev_hash: str = _GENESIS_HASH
        self._initialised = False

        if log_path is None:
            logger.warning(
                "EINVOICING_AUDIT_LOG is not set — audit events will be written to "
                "stderr.  Set this variable to an absolute file path in production."
            )
        else:
            # Warm up _prev_hash from the last line in an existing log file so the
            # chain continues correctly across process restarts.
            self._load_tail()

    @classmethod
    def from_env(cls) -> "AuditLog":
        """Construct from ``EINVOICING_AUDIT_LOG`` and ``EINVOICING_AUDIT_TENANT``."""
        return cls(
            log_path=os.environ.get("EINVOICING_AUDIT_LOG") or None,
            tenant=os.environ.get("EINVOICING_AUDIT_TENANT") or None,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def emit(
        self,
        action: AuditAction,
        document_ref: str,
        content_sha256: str,
        *,
        correlation_id: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> None:
        """Append one audit event to the log.

        Args:
            action:          SIGN, SUBMIT, or CANCEL.
            document_ref:    Invoice or document identifier (number, KSeF ref, flowId …).
            content_sha256:  SHA-256 hex digest of the document payload at the moment
                             the action was taken.
            correlation_id:  Government-assigned reference returned by the platform
                             (KSeF referenceNumber, FR flowId, AEAT ticket …).
            extra:           Optional extra fields (key must be safe ASCII strings).
        """
        with self._lock:
            event: dict = {
                "timestamp": _iso_now(),
                "action": action.value,
                "document_ref": document_ref,
                "content_sha256": content_sha256,
            }
            if self._tenant:
                event["tenant"] = self._tenant
            if correlation_id:
                event["correlation_id"] = correlation_id
            if extra:
                event.update(extra)
            event["prev_hash"] = self._prev_hash

            line = json.dumps(event, ensure_ascii=True, sort_keys=False)
            self._prev_hash = _sha256_of(line)
            event["entry_hash"] = self._prev_hash

            # Re-serialise with the entry hash included (deterministic: same field order).
            final_line = json.dumps(event, ensure_ascii=True, sort_keys=False)

            self._write(final_line)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _write(self, line: str) -> None:
        if self._log_path is None:
            print(line, file=sys.stderr)
            return
        try:
            with open(self._log_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            logger.error("Audit log write failed (%s): %s", self._log_path, exc)

    def _load_tail(self) -> None:
        """Set ``_prev_hash`` from the last entry in an existing log file."""
        assert self._log_path is not None
        path = Path(self._log_path)
        if not path.exists():
            return
        try:
            last_line = _read_last_line(path)
            if last_line:
                entry = json.loads(last_line)
                stored = entry.get("entry_hash", "")
                if stored:
                    self._prev_hash = stored
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read audit log tail for chain init: %s", exc)


def _iso_now() -> str:
    """Return current UTC time as an ISO 8601 string (no microseconds)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_last_line(path: Path) -> str:
    """Return the last non-empty line of *path* efficiently."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            if size == 0:
                return ""
            chunk_size = min(4096, size)
            fh.seek(-chunk_size, 2)
            tail = fh.read(chunk_size)
        lines = tail.split(b"\n")
        for line in reversed(lines):
            stripped = line.strip()
            if stripped:
                return stripped.decode("utf-8", errors="replace")
    except OSError:
        pass
    return ""


# Module-level default instance — lazy, created on first access.
_default_log: Optional[AuditLog] = None
_default_lock = threading.Lock()


def get_audit_log() -> AuditLog:
    """Return the process-wide default AuditLog (created from env vars on first call)."""
    global _default_log
    if _default_log is None:
        with _default_lock:
            if _default_log is None:
                _default_log = AuditLog.from_env()
    return _default_log
