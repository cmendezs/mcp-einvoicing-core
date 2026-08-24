"""Pydantic models for AS4 transmission credentials and receipts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class AS4Credentials(BaseModel):
    """Signing credentials for AS4 message-level security.

    Accepts either file paths or in-memory bytes for the certificate and
    private key. When both are provided, in-memory bytes take precedence.
    """

    certificate_path: Path | None = Field(
        default=None,
        description="Path to PEM-encoded X.509 signing certificate.",
    )
    private_key_path: Path | None = Field(
        default=None,
        description="Path to PEM-encoded private key.",
    )
    certificate_bytes: bytes | None = Field(
        default=None,
        description="In-memory PEM-encoded X.509 signing certificate.",
        exclude=True,
    )
    private_key_bytes: bytes | None = Field(
        default=None,
        description="In-memory PEM-encoded private key.",
        exclude=True,
    )
    private_key_password: str | None = Field(
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


class SBDHIdentifier(BaseModel):
    """A single ``Sender``/``Receiver`` identifier in an SBDH.

    Maps to ``<Sender><Identifier Authority="...">...</Identifier></Sender>``
    (confirmed against the vendored ``specs/peppol/mls/example/snippet-sbdh-*.xml``).
    """

    authority: str
    value: str


class SBDHDocumentIdentification(BaseModel):
    """Maps to SBDH ``<DocumentIdentification>``."""

    standard: str | None = None
    type_version: str | None = None
    instance_identifier: str | None = None
    type: str | None = None
    creation_date_and_time: str | None = None


class SBDHScope(BaseModel):
    """A single ``<BusinessScope><Scope>`` entry (DOCUMENTID, PROCESSID, ...)."""

    type: str
    instance_identifier: str | None = None
    identifier: str | None = None


class StandardBusinessDocumentHeader(BaseModel):
    """Parsed OASIS SBDH 1.0 header, as packaged per the Peppol AS4 Profile
    section 4.9 ("Use of SBDH").

    [NEED: verify] the AS4 Profile 2.0.3 text also mentions ``originalSender``
    and ``finalRecipient`` for four-corner topologies (where C1/C4 differ
    from the C2/C3 Access Points); no locally vendored example carries these,
    so they are not modeled here yet — extend `business_scope` lookups if
    a real message carries them as additional ``Scope`` entries.
    """

    header_version: str | None = None
    sender: SBDHIdentifier | None = None
    receiver: SBDHIdentifier | None = None
    document_identification: SBDHDocumentIdentification | None = None
    business_scope: list[SBDHScope] = Field(default_factory=list)

    def scope_value(self, scope_type: str) -> str | None:
        """Return the ``InstanceIdentifier`` of the first Scope with the given Type."""
        for scope in self.business_scope:
            if scope.type == scope_type:
                return scope.instance_identifier
        return None

    @property
    def mls_to(self) -> str | None:
        """The ``MLS_TO`` Scope value: the Peppol participant ID an MLS
        response for this message should be sent to, if the sender
        requested one (confirmed against
        ``specs/peppol/mls/example/snippet-sbdh-mls-all.xml``)."""
        return self.scope_value("MLS_TO")

    @property
    def mls_type(self) -> str | None:
        """The ``MLS_TYPE`` Scope value (e.g. ``"FAILURE_ONLY"``): which MLS
        responses the sender requested, if any."""
        return self.scope_value("MLS_TYPE")


class AS4InboundMessage(BaseModel):
    """A parsed inbound AS4 UserMessage (AS4-IN-1)."""

    message_id: str
    conversation_id: str | None = None
    sender_id: str | None = None
    receiver_id: str | None = None
    service: str | None = None
    action: str | None = None
    sbdh: StandardBusinessDocumentHeader | None = None
    business_document_xml: bytes | None = Field(default=None, exclude=True)
    signature_valid: bool | None = None
    signature_error: str | None = None
    signer_certificate_der: bytes | None = Field(default=None, exclude=True)
    chain_validation: dict | None = None
    raw_soap_xml: bytes = Field(exclude=True)


class AS4InboundError(BaseModel):
    """Structured representation of an ebMS Error to be sent back to the sender.

    Defaults per the Peppol AS4 Profile 2.0.3 section 4.4 ("Feedback when
    receiver is not serviced"): ``EBMS:0004`` / severity ``failure`` /
    ``PEPPOL:NOT_SERVICED``.
    """

    error_code: str = "EBMS:0004"
    severity: str = "failure"
    short_description: str = "Other error"
    error_detail: str = "PEPPOL:NOT_SERVICED"
    ref_to_message_id: str | None = None


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
    non_repudiation_information: str | None = Field(
        default=None,
        description="Base64-encoded NRI digest value from the receipt, if present.",
    )
    raw_xml: bytes | None = Field(
        default=None,
        description="Raw XML bytes of the receipt signal message.",
        exclude=True,
    )
