"""
Shared logging setup for mcp-einvoicing-core.

Extracted from the identical logging.basicConfig block that appears in
both mcp-facture-electronique-fr/server.py and mcp-fattura-elettronica-it/server.py.

Country adapters call setup_logging() at the top of their server.py instead of
calling logging.basicConfig() directly, ensuring consistent output format across
all country MCP servers.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

_DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(
    level: int | str = logging.INFO,
    format_str: Optional[str] = None,
    stream=sys.stderr,
) -> None:
    """Configure standard logging for an e-invoicing MCP server.

    Args:
        level:      Logging level (logging.INFO, logging.DEBUG, or string 'INFO').
        format_str: Log format string. Defaults to the shared standard format.
        stream:     Output stream (default: stderr, which MCP clients do not read).

    Example:
        from mcp_einvoicing_core.logging_utils import setup_logging
        setup_logging()  # INFO level to stderr
        setup_logging(level=logging.DEBUG)
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format=format_str or _DEFAULT_FORMAT,
        stream=stream,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (thin wrapper kept for consistent import pattern).

    Country adapters import this instead of calling logging.getLogger directly,
    so we can add structured logging or OpenTelemetry here in a future version
    without touching every country package.
    """
    return logging.getLogger(name)
