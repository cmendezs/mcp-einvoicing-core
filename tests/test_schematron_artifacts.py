"""Tests for mcp_einvoicing_core.schematron_artifacts: bundled CEN EN 16931 base validator.

Covers:
  - en16931_base_schematron_validator() returns a working validator
  - A golden Peppol BIS3 example invoice validates clean (zero failed-assert)
  - A mutated invoice (IssueDate removed) trips BR-03
  - Rules renamed or added in CEN 1.3.17 (BR-IG-*, BR-IP-*, UBL-SR-57..59) are
    present in the bundled stylesheet, and the retired BR-AF-*/BR-AG-* are gone
"""

from __future__ import annotations

import importlib.util
import re
import zipfile
from pathlib import Path

import pytest

_SAXON_AVAILABLE = importlib.util.find_spec("saxonche") is not None

pytestmark = pytest.mark.skipif(not _SAXON_AVAILABLE, reason="saxonche extra not installed")

_EXAMPLES_ZIP = Path(__file__).parent.parent / "specs" / "peppol" / "BIS-Billing3-Examples.zip"
_GOLDEN_MEMBER = "rules/examples/base-example.xml"


def _read_golden_invoice() -> bytes:
    with zipfile.ZipFile(_EXAMPLES_ZIP) as zf:
        return zf.read(_GOLDEN_MEMBER)


def _break_br_03(xml_bytes: bytes) -> bytes:
    """Strip the invoice IssueDate so BR-03 (an invoice shall have an issue date) fires."""
    text = xml_bytes.decode("utf-8")
    text = re.sub(r"<cbc:IssueDate>.*?</cbc:IssueDate>", "", text, count=1)
    return text.encode("utf-8")


@pytest.fixture(scope="module")
def validator():
    from mcp_einvoicing_core.schematron_artifacts import en16931_base_schematron_validator

    return en16931_base_schematron_validator()


class TestEn16931BaseSchematronValidator:
    def test_returns_working_validator(self, validator):
        from mcp_einvoicing_core.schematron import SaxonSchematronValidator

        assert isinstance(validator, SaxonSchematronValidator)

    @pytest.mark.skipif(not _EXAMPLES_ZIP.exists(), reason="BIS-Billing3-Examples.zip not present")
    def test_golden_invoice_validates_clean(self, validator):
        xml_bytes = _read_golden_invoice()
        result = validator.validate(xml_bytes, profile="peppol-bis-3", syntax="UBL")
        assert result.is_valid is True
        assert result.errors == []

    @pytest.mark.skipif(not _EXAMPLES_ZIP.exists(), reason="BIS-Billing3-Examples.zip not present")
    def test_missing_issue_date_trips_br_03(self, validator):
        broken = _break_br_03(_read_golden_invoice())
        result = validator.validate(broken, profile="peppol-bis-3", syntax="UBL")
        assert result.is_valid is False
        rule_ids = {e.rule_id for e in result.errors}
        assert "BR-03" in rule_ids

    def test_bundled_stylesheet_carries_cen_1_3_17_rule_ids(self):
        from mcp_einvoicing_core import schematron_artifacts

        text = schematron_artifacts._EN16931_BASE_XSLT.read_text(encoding="utf-8")
        for rule_id in ("BR-IG-01", "BR-IP-01", "UBL-SR-57", "UBL-SR-58", "UBL-SR-59"):
            assert f'"{rule_id}"' in text, rule_id
        for retired in ("BR-AF-01", "BR-AG-01", "BR-CO-25"):
            assert f'"{retired}"' not in text, retired
