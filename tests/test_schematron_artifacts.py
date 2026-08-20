"""Tests for mcp_einvoicing_core.schematron_artifacts: bundled CEN EN 16931 base validator.

Covers:
  - en16931_base_schematron_validator() returns a working validator
  - A golden Peppol BIS3 example invoice validates clean (zero failed-assert)
  - A mutated invoice (DueDate and PaymentTerms/Note both removed on a
    positive PayableAmount) trips BR-CO-25 and only BR-CO-25
"""

from __future__ import annotations

import importlib.util
import re
import zipfile
from pathlib import Path

import pytest

_SAXON_AVAILABLE = importlib.util.find_spec("saxonche") is not None

pytestmark = pytest.mark.skipif(not _SAXON_AVAILABLE, reason="saxonche extra not installed")

_EXAMPLES_ZIP = (
    Path(__file__).parent.parent / "specs" / "peppol" / "BIS-Billing3-Examples.zip"
)
_GOLDEN_MEMBER = "rules/examples/base-example.xml"


def _read_golden_invoice() -> bytes:
    with zipfile.ZipFile(_EXAMPLES_ZIP) as zf:
        return zf.read(_GOLDEN_MEMBER)


def _break_br_co_25(xml_bytes: bytes) -> bytes:
    """Strip DueDate and PaymentTerms so BR-CO-25 fires on a positive PayableAmount."""
    text = xml_bytes.decode("utf-8")
    text = re.sub(r"<cbc:DueDate>.*?</cbc:DueDate>", "", text)
    text = re.sub(r"<cac:PaymentTerms>.*?</cac:PaymentTerms>", "", text, flags=re.DOTALL)
    return text.encode("utf-8")


@pytest.fixture(scope="module")
def validator():
    from mcp_einvoicing_core.schematron_artifacts import en16931_base_schematron_validator

    return en16931_base_schematron_validator()


class TestEn16931BaseSchematronValidator:
    def test_returns_working_validator(self, validator):
        from mcp_einvoicing_core.schematron import SaxonSchematronValidator

        assert isinstance(validator, SaxonSchematronValidator)

    @pytest.mark.skipif(
        not _EXAMPLES_ZIP.exists(), reason="BIS-Billing3-Examples.zip not present"
    )
    def test_golden_invoice_validates_clean(self, validator):
        xml_bytes = _read_golden_invoice()
        result = validator.validate(xml_bytes, profile="peppol-bis-3", syntax="UBL")
        assert result.is_valid is True
        assert result.errors == []

    @pytest.mark.skipif(
        not _EXAMPLES_ZIP.exists(), reason="BIS-Billing3-Examples.zip not present"
    )
    def test_missing_due_date_and_payment_terms_trips_br_co_25(self, validator):
        broken = _break_br_co_25(_read_golden_invoice())
        result = validator.validate(broken, profile="peppol-bis-3", syntax="UBL")
        assert result.is_valid is False
        rule_ids = {e.rule_id for e in result.errors}
        assert rule_ids == {"BR-CO-25"}
