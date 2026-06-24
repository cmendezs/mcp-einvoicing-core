"""Tests for EN16931CreditNote and BillingReference."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from mcp_einvoicing_core.credit_note import BillingReference, EN16931CreditNote
from mcp_einvoicing_core.en16931 import (
    EN16931Address,
    EN16931LineItem,
    EN16931Party,
    EN16931Tax,
)
from mcp_einvoicing_core.wire_formats import (
    EN16931CIIParser,
    EN16931CIISerializer,
    EN16931UBLParser,
    EN16931UBLSerializer,
)


def _make_address() -> EN16931Address:
    return EN16931Address(line_one="1 Rue de Test", city="Paris", postcode="75001", country_code="FR")


def _make_credit_note(**overrides: object) -> EN16931CreditNote:
    defaults: dict = {
        "profile": "urn:cen.eu:en16931:2017",
        "invoice_number": "CN-2026-001",
        "invoice_date": date(2026, 6, 24),
        "invoice_type_code": "381",
        "currency_code": "EUR",
        "billing_reference": BillingReference(
            invoice_number="INV-2026-100",
            issue_date=date(2026, 5, 15),
        ),
        "seller": EN16931Party(name="Seller Co", address=_make_address()),
        "buyer": EN16931Party(name="Buyer Co", address=_make_address()),
        "sum_of_line_net_amounts": Decimal("100.00"),
        "tax_exclusive_amount": Decimal("100.00"),
        "tax_total": Decimal("20.00"),
        "tax_inclusive_amount": Decimal("120.00"),
        "amount_due": Decimal("120.00"),
        "tax_lines": [
            EN16931Tax(
                category="S", rate=Decimal("20"), taxable_amount=Decimal("100.00"),
                tax_amount=Decimal("20.00"),
            )
        ],
        "line_items": [
            EN16931LineItem(
                line_id="1", name="Widget", quantity=Decimal("5"),
                unit_code="C62", unit_price=Decimal("20.00"),
                line_net_amount=Decimal("100.00"), tax_category="S",
                tax_rate=Decimal("20"),
            )
        ],
    }
    defaults.update(overrides)
    return EN16931CreditNote(**defaults)


class TestEN16931CreditNote:
    def test_minimal_credit_note_builds(self) -> None:
        cn = _make_credit_note()
        assert cn.invoice_type_code == "381"
        assert cn.billing_reference.invoice_number == "INV-2026-100"

    def test_preceding_invoice_synced(self) -> None:
        cn = _make_credit_note()
        assert cn.preceding_invoice_reference == "INV-2026-100"
        assert cn.preceding_invoice_date == date(2026, 5, 15)

    def test_invalid_type_code_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_credit_note(invoice_type_code="380")

    def test_type_code_383_accepted(self) -> None:
        cn = _make_credit_note(invoice_type_code="383")
        assert cn.invoice_type_code == "383"

    def test_ubl_round_trip(self) -> None:
        cn = _make_credit_note()
        xml_bytes = EN16931UBLSerializer().serialize(cn)
        assert b"CreditNote" in xml_bytes
        parsed = EN16931UBLParser().parse(xml_bytes)
        assert parsed.invoice_type_code == "381"
        assert parsed.invoice_number == "CN-2026-001"
        assert parsed.preceding_invoice_reference == "INV-2026-100"

    def test_cii_round_trip(self) -> None:
        cn = _make_credit_note()
        xml_bytes = EN16931CIISerializer().serialize(cn)
        assert b"<ram:TypeCode>381</ram:TypeCode>" in xml_bytes
        parsed = EN16931CIIParser().parse(xml_bytes)
        assert parsed.invoice_type_code == "381"
        assert parsed.invoice_number == "CN-2026-001"
        assert parsed.preceding_invoice_reference == "INV-2026-100"
