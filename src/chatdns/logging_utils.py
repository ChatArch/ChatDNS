"""Logging helpers for ChatDNS."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal


def setup_logger(
    name: str,
    log_file: str | Path | None = None,
    console: bool = True,
    log_level: str | int = "INFO",
    file_log_level: str | int | None = None,
    console_log_level: str | int | None = None,
    format_type: Literal["simple", "detailed"] = "simple",
    file_mode: Literal["w", "a"] = "w",
    encoding: str = "utf-8",
) -> logging.Logger:
    """Configure and return a logger instance."""
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.setLevel(log_level)

    if format_type == "simple":
        console_fmt = "%(levelname)s: %(message)s"
        file_fmt = "%(asctime)s - %(levelname)s: %(message)s"
    else:
        console_fmt = "%(asctime)s - %(name)s - %(levelname)s: %(message)s"
        file_fmt = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"

    if console:
        handler = logging.StreamHandler()
        handler.setLevel(console_log_level or log_level)
        handler.setFormatter(logging.Formatter(console_fmt))
        logger.addHandler(handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_path, mode=file_mode, encoding=encoding)
        handler.setLevel(file_log_level or log_level)
        handler.setFormatter(logging.Formatter(file_fmt))
        logger.addHandler(handler)

    return logger
