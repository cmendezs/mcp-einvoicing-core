"""Tests for the CORE-2 typed submission contract (SubmissionMetadata/SearchCriteria)."""

from __future__ import annotations

import pytest

from mcp_einvoicing_core.base_server import (
    BaseLifecycleManager,
    SearchCriteria,
    SubmissionMetadata,
    SubmitResult,
)


class _CountrySubmissionMetadata(SubmissionMetadata):
    session_token: str | None = None


class _CountrySearchCriteria(SearchCriteria):
    date_from: str | None = None


class _FakeLifecycleManager(BaseLifecycleManager):
    async def submit_document(
        self, document: bytes | str, metadata: SubmissionMetadata
    ) -> SubmitResult:
        return SubmitResult(invoice_ref="ref-1", raw={"metadata": metadata.model_dump()})

    async def get_document_status(self, document_id: str) -> dict:
        return {"document_id": document_id, "status": "submitted"}

    async def search_documents(self, criteria: SearchCriteria) -> list[dict]:
        return [{"criteria": criteria.model_dump()}]


class TestSubmissionMetadata:
    def test_base_class_allows_extra_fields(self) -> None:
        metadata = SubmissionMetadata(filename="invoice.xml")
        assert metadata.model_dump() == {"filename": "invoice.xml"}

    def test_subclass_typed_field_is_validated(self) -> None:
        metadata = _CountrySubmissionMetadata(session_token="abc123")
        assert metadata.session_token == "abc123"

    def test_subclass_still_allows_extra_fields(self) -> None:
        metadata = _CountrySubmissionMetadata(session_token="abc123", form_code={"a": "b"})
        assert metadata.model_dump() == {"session_token": "abc123", "form_code": {"a": "b"}}


class TestSearchCriteria:
    def test_base_class_allows_extra_fields(self) -> None:
        criteria = SearchCriteria(subject_type="Subject1")
        assert criteria.model_dump() == {"subject_type": "Subject1"}

    def test_subclass_typed_field_is_validated(self) -> None:
        criteria = _CountrySearchCriteria(date_from="2026-01-01")
        assert criteria.date_from == "2026-01-01"


class TestBaseLifecycleManagerTypedContract:
    @pytest.mark.asyncio
    async def test_submit_document_accepts_typed_metadata(self) -> None:
        manager = _FakeLifecycleManager()
        metadata = _CountrySubmissionMetadata(session_token="abc123")
        result = await manager.submit_document(b"<xml/>", metadata)
        assert result.invoice_ref == "ref-1"
        assert result.raw == {"metadata": {"session_token": "abc123"}}

    @pytest.mark.asyncio
    async def test_search_documents_accepts_typed_criteria(self) -> None:
        manager = _FakeLifecycleManager()
        criteria = _CountrySearchCriteria(date_from="2026-01-01")
        results = await manager.search_documents(criteria)
        assert results == [{"criteria": {"date_from": "2026-01-01"}}]

    @pytest.mark.asyncio
    async def test_submit_lifecycle_status_default_raises_not_implemented(self) -> None:
        manager = _FakeLifecycleManager()
        with pytest.raises(NotImplementedError):
            await manager.submit_lifecycle_status("ref-1", "Approved", SubmissionMetadata())

    @pytest.mark.asyncio
    async def test_submit_lifecycle_status_default_metadata_is_none(self) -> None:
        manager = _FakeLifecycleManager()
        with pytest.raises(NotImplementedError):
            await manager.submit_lifecycle_status("ref-1", "Approved")
