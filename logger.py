import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True) 

LOG_FILE_NAME = os.getenv("LOG_FILE", "instagram.log")
LOG_FILE = os.path.join(LOG_DIR, LOG_FILE_NAME)

LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "14"))
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s"
CONSOLE_LOG_FORMAT = "%(asctime)s %(levelname_color)s %(message)s"


class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[36m",    # cyan
        logging.INFO: "\033[32m",     # green
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",    # red
        logging.CRITICAL: "\033[35m", # magenta
    }
    HIGHLIGHT_COLORS = {
        "start": "\033[1;36m",    # bold cyan
        "progress": "\033[1;34m", # bold blue
        "success": "\033[1;32m",  # bold green
        "summary": "\033[1;35m",  # bold magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        highlight_color = self.HIGHLIGHT_COLORS.get(getattr(record, "highlight", None))
        if highlight_color:
            record.levelname_color = f"[{record.levelname}]"
            return f"{highlight_color}{super().format(record)}{self.RESET}"

        color = self.COLORS.get(record.levelno, "")
        record.levelname_color = f"{color}[{record.levelname}]{self.RESET}" if color else f"[{record.levelname}]"
        return super().format(record)


logger = logging.getLogger("instagram")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
logger.handlers.clear()
logger.propagate = False

file_handler = TimedRotatingFileHandler(
    LOG_FILE,
    when="midnight",
    interval=1,
    backupCount=LOG_RETENTION_DAYS,
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColorFormatter(CONSOLE_LOG_FORMAT))

logger.addHandler(file_handler)
logger.addHandler(console_handler)
