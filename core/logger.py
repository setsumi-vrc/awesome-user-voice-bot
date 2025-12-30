import logging
import json
from logging import LogRecord
import sys


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging in production."""
    
    def format(self, record: LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def get_logger(name: str, json_mode: bool = False) -> logging.Logger:
    """Get a logger instance with optional JSON formatting.
    
    Args:
        name: Logger name (typically __name__)
        json_mode: Use JSON formatter (True for production, False for dev)
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if json_mode:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                "[%(asctime)s] %(levelname)s [%(module)s] %(message)s"
            )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
