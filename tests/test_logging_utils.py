"""Tests for mcp_einvoicing_core.logging_utils."""

from __future__ import annotations

import logging

from mcp_einvoicing_core.logging_utils import get_logger, setup_logging


class TestGetLogger:
    def test_returns_logger(self) -> None:
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)

    def test_name_matches(self) -> None:
        logger = get_logger("mcp_einvoicing_core.test")
        assert logger.name == "mcp_einvoicing_core.test"

    def test_same_name_same_instance(self) -> None:
        assert get_logger("same.name") is get_logger("same.name")


class TestSetupLogging:
    def test_integer_level_does_not_raise(self) -> None:
        setup_logging(level=logging.DEBUG)

    def test_string_level_does_not_raise(self) -> None:
        setup_logging(level="WARNING")

    def test_invalid_string_does_not_raise(self) -> None:
        # logging.basicConfig is a no-op when handlers exist (as pytest sets them up),
        # so we can only assert the call does not raise.
        setup_logging(level="NOTAREALLEVEL")

    def test_custom_format_accepted(self) -> None:
        setup_logging(format_str="%(message)s")
