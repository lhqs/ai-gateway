import logging

from uvicorn.config import LOGGING_CONFIG
from uvicorn.logging import AccessFormatter, DefaultFormatter


LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_FORMAT = "%(levelprefix)s %(asctime)s %(message)s"
ACCESS_LOG_FORMAT = (
    '%(levelprefix)s %(asctime)s %(client_addr)s - "%(request_line)s" %(status_code)s'
)


def configure_logging() -> None:
    """Keep Uvicorn and application logs timestamped without changing deployment commands."""
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = DEFAULT_LOG_FORMAT
    LOGGING_CONFIG["formatters"]["default"]["datefmt"] = LOG_DATE_FORMAT
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = ACCESS_LOG_FORMAT
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = LOG_DATE_FORMAT

    default_formatter = DefaultFormatter(
        DEFAULT_LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        use_colors=None,
    )
    access_formatter = AccessFormatter(ACCESS_LOG_FORMAT, datefmt=LOG_DATE_FORMAT, use_colors=None)

    _set_formatter("uvicorn", default_formatter)
    _set_formatter("uvicorn.error", default_formatter)
    _set_formatter("uvicorn.access", access_formatter)


def _set_formatter(logger_name: str, formatter: logging.Formatter) -> None:
    logger = logging.getLogger(logger_name)
    for handler in logger.handlers:
        handler.setFormatter(formatter)
