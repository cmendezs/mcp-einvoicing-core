"""Pydantic models for AS4 transmission credentials and receipts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class AS4Credentials(BaseModel):
    """Signing credentials for AS4 message-level security.

    Accepts either file paths or in-memory bytes for the certificate and
    private key. When both are provided, in-memory bytes take precedence.
    """

    certificate_path: Optional[Path] = Field(
        default=None,
        description="Path to PEM-encoded X.509 signing certificate.",
    )
    private_key_path: Optional[Path] = Field(
        default=None,
        description="Path to PEM-encoded private key.",
    )
    certificate_bytes: Optional[bytes] = Field(
        default=None,
        description="In-memory PEM-encoded X.509 signing certificate.",
        exclude=True,
    )
    private_key_bytes: Optional[bytes] = Field(
        default=None,
        description="In-memory PEM-encoded private key.",
        exclude=True,
    )
    private_key_password: Optional[str] = Field(
        default=None,
        description="Password for encrypted private key.",
        exclude=True,
    )

    def load_certificate(self) -> bytes:
        """Return certificate bytes, loading from file if needed."""
        if self.certificate_bytes:
            return self.certificate_bytes
        if self.certificate_path:
            return self.certificate_path.read_bytes()
        raise ValueError("No certificate provided (set certificate_path or certificate_bytes).")

    def load_private_key(self) -> bytes:
        """Return private key bytes, loading from file if needed."""
        if self.private_key_bytes:
            return self.private_key_bytes
        if self.private_key_path:
            return self.private_key_path.read_bytes()
        raise ValueError("No private key provided (set private_key_path or private_key_bytes).")


class AS4Receipt(BaseModel):
    """Parsed AS4 signal message receipt.

    Returned by the receiving Access Point as a synchronous response to
    the AS4 UserMessage. Contains non-repudiation information per the
    Peppol AS4 profile.
    """

    message_id: str = Field(
        description="ebMS3 MessageId of the receipt signal message.",
    )
    ref_to_message_id: str = Field(
        description="ebMS3 RefToMessageId, matching the original UserMessage MessageId.",
    )
    timestamp: datetime = Field(
        description="Timestamp from the receipt signal message.",
    )
    non_repudiation_information: Optional[str] = Field(
        default=None,
        description="Base64-encoded NRI digest value from the receipt, if present.",
    )
    raw_xml: Optional[bytes] = Field(
        default=None,
        description="Raw XML bytes of the receipt signal message.",
        exclude=True,
    )
