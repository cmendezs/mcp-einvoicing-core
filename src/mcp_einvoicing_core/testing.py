"""Test fixture helpers for mcp-einvoicing-core.

Provides InvoiceFixtureFactory, a factory that produces minimal-valid
EN16931Invoice objects for use in country package test suites.

Country packages call the factory in their conftest.py:

    from mcp_einvoicing_core.testing import InvoiceFixtureFactory
    import pytest

    @pytest.fixture
    def minimal_invoice():
        return InvoiceFixtureFactory.invoice(
            profile_urn="urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:en16931",
        )

Country packages that extend EN16931Invoice (e.g. ZUGFeRDInvoice) should
use the factory to build the base and then convert or supplement the result:

    @pytest.fixture
    def minimal_zugferd_invoice():
        base = InvoiceFixtureFactory.invoice(ZUGFeRDProfile.EN_16931.value)
        return ZUGFeRDInvoice(**base.model_dump(), profile=ZUGFeRDProfile.EN_16931)

This module has no runtime dependencies beyond what mcp-einvoicing-core already
requires.  It is safe to import in production code (no pytest dependency at runtime).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from mcp_einvoicing_core.en16931 import (
    EN16931Address,
    EN16931Invoice,
    EN16931LineItem,
    EN16931Party,
    EN16931PaymentMeans,
    EN16931Tax,
)


class InvoiceFixtureFactory:
    """Factory for minimal-valid EN16931Invoice objects.

    All methods return freshly constructed objects (no shared mutable state).
    Override individual fields by passing keyword arguments; the factory fills
    in every other required field with a sensible default.
    """

    # ── Building blocks ───────────────────────────────────────────────────────

    @staticmethod
    def address(
        *,
        line_one: str = "Hauptstrasse 1",
        city: str = "Berlin",
        postcode: str = "10115",
        country_code: str = "DE",
        region: str | None = None,
    ) -> EN16931Address:
        """Return a minimal valid EN16931Address."""
        return EN16931Address(
            line_one=line_one,
            city=city,
            postcode=postcode,
            country_code=country_code,
            region=region,
        )

    @staticmethod
    def party(
        *,
        name: str = "Test Company GmbH",
        country_code: str = "DE",
        vat_id: str | None = "DE123456789",
    ) -> EN16931Party:
        """Return a minimal valid EN16931Party."""
        return EN16931Party(
            name=name,
            address=InvoiceFixtureFactory.address(country_code=country_code),
            vat_id=vat_id,
        )

    @staticmethod
    def tax_line(
        *,
        category: str = "S",
        rate: Decimal | str = "19",
        taxable_amount: Decimal | str = "100.00",
        tax_amount: Decimal | str = "19.00",
    ) -> EN16931Tax:
        """Return a minimal valid EN16931Tax line."""
        return EN16931Tax(
            category=category,
            rate=Decimal(str(rate)),
            taxable_amount=Decimal(str(taxable_amount)),
            tax_amount=Decimal(str(tax_amount)),
        )

    @staticmethod
    def line_item(
        *,
        line_id: str = "1",
        name: str = "Test Service",
        quantity: Decimal | str = "1",
        unit_code: str = "C62",
        unit_price: Decimal | str = "100.00",
        line_net_amount: Decimal | str = "100.00",
        tax_category: str = "S",
        tax_rate: Decimal | str = "19",
    ) -> EN16931LineItem:
        """Return a minimal valid EN16931LineItem."""
        return EN16931LineItem(
            line_id=line_id,
            name=name,
            quantity=Decimal(str(quantity)),
            unit_code=unit_code,
            unit_price=Decimal(str(unit_price)),
            line_net_amount=Decimal(str(line_net_amount)),
            tax_category=tax_category,
            tax_rate=Decimal(str(tax_rate)),
        )

    @staticmethod
    def payment_means(
        *,
        type_code: str = "58",
        iban: str | None = "DE89370400440532013000",
    ) -> EN16931PaymentMeans:
        """Return a minimal valid EN16931PaymentMeans (SEPA credit transfer)."""
        return EN16931PaymentMeans(type_code=type_code, iban=iban)

    # ── Full invoice ──────────────────────────────────────────────────────────

    @staticmethod
    def invoice(
        profile_urn: str,
        *,
        invoice_number: str = "TEST-001",
        invoice_date: date | None = None,
        seller: EN16931Party | None = None,
        buyer: EN16931Party | None = None,
        tax_lines: list[EN16931Tax] | None = None,
        line_items: list[EN16931LineItem] | None = None,
        net_amount: Decimal | str = "100.00",
        vat_amount: Decimal | str = "19.00",
        gross_amount: Decimal | str = "119.00",
        currency_code: str = "EUR",
    ) -> EN16931Invoice:
        """Return a minimal valid EN16931Invoice for the given profile URN.

        All monetary amounts default to a single 100 EUR + 19% VAT scenario.
        Supply *line_items* to get a profile above BASIC WL.

        Args:
            profile_urn:   BT-24 GuidelineID URN. Use the country enum value
                           (e.g. ZUGFeRDProfile.EN_16931.value) or a raw URN string.
            invoice_number: BT-1.
            invoice_date:   BT-2 (defaults to today).
            seller:         BG-4 (defaults to a German test seller).
            buyer:          BG-7 (defaults to a German test buyer).
            tax_lines:      BG-23 (defaults to one 19% standard-rate line).
            line_items:     BG-25 (absent by default — MINIMUM / BASIC WL compatible).
            net_amount:     BT-109 tax-exclusive total.
            vat_amount:     BT-110 total VAT.
            gross_amount:   BT-112 tax-inclusive total.
            currency_code:  BT-5.
        """
        net = Decimal(str(net_amount))
        vat = Decimal(str(vat_amount))
        gross = Decimal(str(gross_amount))

        return EN16931Invoice(
            profile=profile_urn,
            invoice_number=invoice_number,
            invoice_date=invoice_date or date.today(),
            currency_code=currency_code,
            seller=seller or InvoiceFixtureFactory.party(name="Test Seller GmbH"),
            buyer=buyer or InvoiceFixtureFactory.party(name="Test Buyer AG"),
            sum_of_line_net_amounts=net,
            tax_exclusive_amount=net,
            tax_total=vat,
            tax_inclusive_amount=gross,
            amount_due=gross,
            tax_lines=tax_lines or [InvoiceFixtureFactory.tax_line(
                taxable_amount=net,
                tax_amount=vat,
            )],
            line_items=line_items or [],
        )
