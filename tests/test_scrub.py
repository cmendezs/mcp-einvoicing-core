"""Tests for mcp_einvoicing_core.base_server.scrub() — the P1.5 output-masking layer."""

from __future__ import annotations

import importlib

import pytest

from mcp_einvoicing_core import base_server


@pytest.fixture(autouse=True)
def _masking_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("EINVOICING_DISABLE_LLM_MASKING", raising=False)
    importlib.reload(base_server)
    yield
    importlib.reload(base_server)


def test_scrub_redacts_iban_in_string():
    assert base_server.scrub("IBAN DE89370400440532013000 on file") == (
        "IBAN [IBAN REDACTED] on file"
    )


def test_scrub_redacts_uppercase_bic_in_string():
    assert base_server.scrub("BIC COBADEFFXXX on file") == "BIC [BIC REDACTED] on file"


def test_scrub_redacts_lowercase_iban():
    assert base_server.scrub("de89370400440532013000") == "[IBAN REDACTED]"


def test_scrub_does_not_redact_lowercase_bic():
    # BIC matching is intentionally case-sensitive; documented tradeoff.
    assert base_server.scrub("cobadeffxxx") == "cobadeffxxx"


def test_scrub_does_not_double_redact_its_own_placeholder():
    # Regression: sequential IBAN-then-BIC substitution used to let the BIC
    # pattern match the word REDACTED inside the IBAN placeholder it had just
    # produced, corrupting the output.
    result = base_server.scrub("DE89370400440532013000")
    assert result == "[IBAN REDACTED]"
    assert "REDACTED]]" not in result


def test_scrub_does_not_redact_ordinary_prose_words():
    # Regression: the BIC pattern used to match any bare 8- or 11-letter word
    # case-insensitively, corrupting ordinary text.
    text = "encoding currency delivery Deutschland"
    assert base_server.scrub(text) == text


def test_scrub_preserves_xml_declaration():
    xml = "<?xml version='1.0' encoding='UTF-8'?><IBANID>DE89370400440532013000</IBANID>"
    result = base_server.scrub(xml)
    assert "encoding='UTF-8'" in result
    assert "[IBAN REDACTED]" in result
    assert "DE89370400440532013000" not in result


def test_scrub_recurses_dict_and_list():
    data = {
        "payment_means": {"iban": "DE89370400440532013000", "bic": "COBADEFFXXX"},
        "notes": ["ref DE89370400440532013000", "no PII here"],
        "amount": 119.0,
    }
    result = base_server.scrub(data)
    assert result["payment_means"]["iban"] == "[IBAN REDACTED]"
    assert result["payment_means"]["bic"] == "[BIC REDACTED]"
    assert result["notes"][0] == "ref [IBAN REDACTED]"
    assert result["notes"][1] == "no PII here"
    assert result["amount"] == 119.0


def test_scrub_disabled_via_env_var(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EINVOICING_DISABLE_LLM_MASKING", "1")
    importlib.reload(base_server)
    try:
        assert base_server.scrub("DE89370400440532013000") == "DE89370400440532013000"
    finally:
        importlib.reload(base_server)
