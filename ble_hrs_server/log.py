import inspect
import logging
import sys

import loguru

from .conf import config

logger = loguru.logger


logger.remove()
logger_id = logger.add(
    sys.stdout,
    level=config.log_level,
    diagnose=False,
)


# https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
class LoguruHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(
            depth=depth,
            exception=record.exc_info,
        ).log(level, record.getMessage())


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "default": {"class": "ble_hrs_server.log.LoguruHandler"},
    },
    "loggers": {
        "uvicorn.error": {"handlers": ["default"], "level": "DEBUG"},
        "uvicorn.access": {"handlers": ["default"], "level": "DEBUG"},
    },
}
