"""Tests for BaseUBLDocument."""

from datetime import date

import pytest
from pydantic import Field, ValidationError

from mcp_einvoicing_core.peppol import PeppolParticipantId
from mcp_einvoicing_core.ubl_documents import BaseUBLDocument


def _make_participant(value: str = "9999:test") -> PeppolParticipantId:
    return PeppolParticipantId.parse(value)


def _make_document(**overrides: object) -> BaseUBLDocument:
    defaults: dict = {
        "document_id": "ORDER-2026-001",
        "issue_date": date(2026, 8, 27),
        "customization_id": "urn:fdc:peppol.eu:poacc:trns:order:3",
        "profile_id": "urn:fdc:peppol.eu:poacc:bis:order_only:3",
        "sender": _make_participant("0195:SGUEN200212345Z"),
        "receiver": _make_participant("0195:SGUEN200254321Z"),
    }
    defaults.update(overrides)
    return BaseUBLDocument(**defaults)


class TestBaseUBLDocument:
    def test_minimal_document_builds(self) -> None:
        doc = _make_document()
        assert doc.document_id == "ORDER-2026-001"
        assert doc.sender.scheme == "0195"
        assert doc.sender.value == "SGUEN200212345Z"

    def test_missing_required_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BaseUBLDocument(
                issue_date=date(2026, 8, 27),
                customization_id="urn:fdc:peppol.eu:poacc:trns:order:3",
                profile_id="urn:fdc:peppol.eu:poacc:bis:order_only:3",
                sender=_make_participant(),
                receiver=_make_participant(),
            )

    def test_subclass_adds_document_type_specific_fields(self) -> None:
        class OrderStub(BaseUBLDocument):
            note: str | None = Field(default=None)

        order = OrderStub(
            document_id="ORDER-2026-002",
            issue_date=date(2026, 8, 27),
            customization_id="urn:fdc:peppol.eu:poacc:trns:order:3",
            profile_id="urn:fdc:peppol.eu:poacc:bis:order_only:3",
            sender=_make_participant(),
            receiver=_make_participant(),
            note="rush order",
        )
        assert order.note == "rush order"
        assert isinstance(order, BaseUBLDocument)
