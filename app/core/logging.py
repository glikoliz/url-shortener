import logging
import sys

from app.config import settings


class ColourizedFormatter(logging.Formatter):
    """A custom log formatter that adds colors and highlights Redis."""

    level_name_colors = {
        logging.DEBUG: "\x1b[36m",  # Cyan
        logging.INFO: "\x1b[32m",  # Green
        logging.WARNING: "\x1b[33m",  # Yellow
        logging.ERROR: "\x1b[31m",  # Red
        logging.CRITICAL: "\x1b[1;31m",  # Bold Red
    }

    REDIS_COLOR = "\x1b[35m"  # Magenta
    reset = "\x1b[0m"

    def format(self, record):
        log_time = self.formatTime(record, "%H:%M:%S")

        message = record.getMessage()
        is_cache = "Cache" in message or "Redis" in message

        color = self.level_name_colors.get(record.levelno, "")

        if is_cache:
            level_name = f"{self.REDIS_COLOR}{record.levelname:<8}{self.reset}"
            message = f"{self.REDIS_COLOR}{message}{self.reset}"
        else:
            level_name = f"{color}{record.levelname:<8}{self.reset}"

        return f"{log_time} {level_name} {message}"


def setup_logging():
    # Configure root logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColourizedFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)
    root_logger.handlers = [handler]

    for logger_name in ("uvicorn", "uvicorn.error", "fastapi"):
        logger = logging.getLogger(logger_name)
        logger.handlers = []
        logger.propagate = True

    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers = []
    access_logger.propagate = False

    logging.info("Logging initialized (Redis highlighted, Access logs unified)")
