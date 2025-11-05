"""Application-wide logging configuration."""
from __future__ import annotations

import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def configure_logging(debug: bool = False) -> None:
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG if debug else logging.INFO)
    logger.remove()
    logger.add(
        sys.stdout,
        colorize=True,
        level="DEBUG" if debug else "INFO",
        backtrace=debug,
        diagnose=debug,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )
