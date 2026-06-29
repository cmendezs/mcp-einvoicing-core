"""Tests for mcp_einvoicing_core.archive."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mcp_einvoicing_core.archive import ArchiveMetadata, BaseArchiveProvider


class TestArchiveMetadata:
    def test_minimal_construction(self) -> None:
        now = datetime.now(timezone.utc)
        meta = ArchiveMetadata(
            document_id="doc-001",
            document_hash="abcdef1234567890" * 4,
            archive_timestamp=now,
            retention_until=now,
            format_id="FatturaPA-1.2.3",
        )
        assert meta.document_id == "doc-001"
        assert meta.signer_id is None
        assert meta.raw == {}

    def test_full_construction(self) -> None:
        now = datetime.now(timezone.utc)
        meta = ArchiveMetadata(
            document_id="doc-002",
            document_hash="a" * 64,
            archive_timestamp=now,
            retention_until=now,
            format_id="NF-e-4.00",
            signer_id="IT12345678901",
            raw={"provider_ref": "xyz"},
        )
        assert meta.signer_id == "IT12345678901"
        assert meta.raw["provider_ref"] == "xyz"


class TestBaseArchiveProvider:
    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            BaseArchiveProvider()  # type: ignore[abstract]
