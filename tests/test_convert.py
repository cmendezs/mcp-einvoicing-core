"""Tests for convert_wire_format."""

from datetime import date
from decimal import Decimal

import pytest

from mcp_einvoicing_core.convert import Syntax, convert_wire_format
from mcp_einvoicing_core.en16931 import (
    EN16931Address,
    EN16931Invoice,
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


def _make_invoice() -> EN16931Invoice:
    addr = EN16931Address(line_one="1 Rue Test", city="Paris", postcode="75001", country_code="FR")
    return EN16931Invoice(
        profile="urn:cen.eu:en16931:2017",
        invoice_number="INV-001",
        invoice_date=date(2026, 6, 24),
        currency_code="EUR",
        seller=EN16931Party(name="Seller", address=addr),
        buyer=EN16931Party(name="Buyer", address=addr),
        sum_of_line_net_amounts=Decimal("100.00"),
        tax_exclusive_amount=Decimal("100.00"),
        tax_total=Decimal("20.00"),
        tax_inclusive_amount=Decimal("120.00"),
        amount_due=Decimal("120.00"),
        tax_lines=[
            EN16931Tax(category="S", rate=Decimal("20"), taxable_amount=Decimal("100.00"),
                       tax_amount=Decimal("20.00"))
        ],
        line_items=[
            EN16931LineItem(line_id="1", name="Item", quantity=Decimal("1"),
                           unit_code="C62", unit_price=Decimal("100.00"),
                           line_net_amount=Decimal("100.00"), tax_category="S",
                           tax_rate=Decimal("20"))
        ],
    )


class TestConvertWireFormat:
    def test_cii_to_ubl(self) -> None:
        cii_bytes = EN16931CIISerializer().serialize(_make_invoice())
        ubl_bytes = convert_wire_format(cii_bytes, target=Syntax.UBL)
        parsed = EN16931UBLParser().parse(ubl_bytes)
        assert parsed.invoice_number == "INV-001"
        assert b"Invoice" in ubl_bytes

    def test_ubl_to_cii(self) -> None:
        ubl_bytes = EN16931UBLSerializer().serialize(_make_invoice())
        cii_bytes = convert_wire_format(ubl_bytes, target=Syntax.CII)
        parsed = EN16931CIIParser().parse(cii_bytes)
        assert parsed.invoice_number == "INV-001"
        assert b"CrossIndustryInvoice" in cii_bytes

    def test_same_syntax_raises(self) -> None:
        ubl_bytes = EN16931UBLSerializer().serialize(_make_invoice())
        with pytest.raises(ValueError, match="already in UBL"):
            convert_wire_format(ubl_bytes, target=Syntax.UBL)

    def test_undetectable_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot detect"):
            convert_wire_format(b"<root>unknown</root>", target=Syntax.UBL)

    def test_round_trip_preserves_amounts(self) -> None:
        inv = _make_invoice()
        cii_bytes = EN16931CIISerializer().serialize(inv)
        ubl_bytes = convert_wire_format(cii_bytes, target=Syntax.UBL)
        back_to_cii = convert_wire_format(ubl_bytes, target=Syntax.CII)
        parsed = EN16931CIIParser().parse(back_to_cii)
        assert parsed.amount_due == Decimal("120.00")
        assert parsed.tax_total == Decimal("20.00")
