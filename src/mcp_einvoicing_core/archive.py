"""Archive provider abstraction for legally compliant document archiving.

Public API
----------
ArchiveMetadata
    Pydantic model representing the metadata of an archived document.

BaseArchiveProvider
    Abstract base class for archiving integrations. Country packages
    subclass this to implement jurisdiction-specific archiving (e.g.
    IT conservazione sostitutiva per AgID circolare 65/2014).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ArchiveMetadata(BaseModel):
    """Metadata returned when a document is archived."""

    document_id: str = Field(description="Unique identifier assigned by the archive provider.")
    document_hash: str = Field(description="SHA-256 hex digest of the archived document bytes.")
    archive_timestamp: datetime = Field(description="UTC timestamp when the document was archived.")
    retention_until: datetime = Field(description="UTC timestamp until which the document must be retained.")
    format_id: str = Field(description="Format identifier (e.g. 'FatturaPA-1.2.3', 'NF-e-4.00').")
    signer_id: Optional[str] = Field(default=None, description="Identifier of the signer, if the document was signed.")
    raw: dict = Field(default_factory=dict, description="Full provider-specific response.")


class BaseArchiveProvider(ABC):
    """Abstract base class for document archiving integrations.

    Country packages extend this to implement jurisdiction-specific
    legally compliant archiving. The contract covers the four core
    operations: archive, retrieve, list, and verify integrity.
    """

    @abstractmethod
    async def archive_document(
        self, document: bytes, metadata: dict
    ) -> ArchiveMetadata:
        """Archive *document* and return its metadata.

        Args:
            document: Raw document bytes to archive.
            metadata: Provider-specific metadata (format, signer info,
                retention policy, etc.).

        Returns:
            Metadata describing the archived document.
        """

    @abstractmethod
    async def retrieve_document(
        self, document_id: str
    ) -> tuple[bytes, ArchiveMetadata]:
        """Retrieve an archived document by its ID.

        Args:
            document_id: The identifier returned by ``archive_document``.

        Returns:
            A tuple of (document_bytes, metadata).
        """

    @abstractmethod
    async def list_documents(
        self, criteria: dict
    ) -> list[ArchiveMetadata]:
        """Query archived documents matching *criteria*.

        Args:
            criteria: Provider-specific search criteria (date range,
                format, signer, etc.).

        Returns:
            List of matching document metadata records.
        """

    @abstractmethod
    async def verify_integrity(self, document_id: str) -> bool:
        """Verify the integrity of an archived document.

        Args:
            document_id: The identifier returned by ``archive_document``.

        Returns:
            True if the document hash and timestamp chain are valid.
        """
