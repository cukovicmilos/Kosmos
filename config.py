"""
Configuration module for Kosmos Telegram Bot.
Loads environment variables and sets up logging.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project root directory
ROOT_DIR = Path(__file__).parent

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env file")

# Database configuration
DB_PATH = os.getenv("DB_PATH", "kosmos.db")
DB_FULL_PATH = ROOT_DIR / DB_PATH

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = ROOT_DIR / "log"
LOG_FILE = LOG_DIR / "app.log"

# Timezone configuration
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Europe/Belgrade")

# Available timezone options for user selection
# Format: (display_name, timezone_id)
TIMEZONE_OPTIONS = [
    # Europe
    ("🇷🇸 Europe/Belgrade", "Europe/Belgrade"),
    ("🇬🇧 Europe/London", "Europe/London"),
    ("🇩🇪 Europe/Berlin", "Europe/Berlin"),
    ("🇫🇷 Europe/Paris", "Europe/Paris"),
    ("🇮🇹 Europe/Rome", "Europe/Rome"),
    ("🇪🇸 Europe/Madrid", "Europe/Madrid"),
    ("🇷🇺 Europe/Moscow", "Europe/Moscow"),
    # Americas
    ("🇺🇸 America/New_York", "America/New_York"),
    ("🇺🇸 America/Chicago", "America/Chicago"),
    ("🇺🇸 America/Denver", "America/Denver"),
    ("🇺🇸 America/Los_Angeles", "America/Los_Angeles"),
    ("🇨🇦 America/Toronto", "America/Toronto"),
    ("🇧🇷 America/Sao_Paulo", "America/Sao_Paulo"),
    # Asia
    ("🇨🇳 Asia/Shanghai", "Asia/Shanghai"),
    ("🇯🇵 Asia/Tokyo", "Asia/Tokyo"),
    ("🇮🇳 Asia/Kolkata", "Asia/Kolkata"),
    ("🇦🇪 Asia/Dubai", "Asia/Dubai"),
    # Oceania
    ("🇦🇺 Australia/Sydney", "Australia/Sydney"),
]

# Supported languages
SUPPORTED_LANGUAGES = ["en", "sr-lat"]
DEFAULT_LANGUAGE = "en"

# Time formats
TIME_FORMAT_12H = "12h"
TIME_FORMAT_24H = "24h"

# Network timeout configuration (in seconds)
TELEGRAM_CONNECT_TIMEOUT = float(os.getenv("TELEGRAM_CONNECT_TIMEOUT", "20.0"))  # Connection timeout
TELEGRAM_READ_TIMEOUT = float(os.getenv("TELEGRAM_READ_TIMEOUT", "30.0"))  # Read timeout
TELEGRAM_WRITE_TIMEOUT = float(os.getenv("TELEGRAM_WRITE_TIMEOUT", "30.0"))  # Write timeout
TELEGRAM_POOL_TIMEOUT = float(os.getenv("TELEGRAM_POOL_TIMEOUT", "10.0"))  # Pool timeout

# Monitoring configuration
MAX_CONSECUTIVE_TIMEOUTS = int(os.getenv("MAX_CONSECUTIVE_TIMEOUTS", "3"))  # Alert threshold


def setup_logging():
    """
    Set up logging configuration with file and console handlers.
    Creates log directory if it doesn't exist.
    """
    # Create log directory if it doesn't exist
    LOG_DIR.mkdir(exist_ok=True)

    # Configure logging format
    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Create formatter
    formatter = logging.Formatter(log_format, date_format)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(LOG_LEVEL)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(LOG_LEVEL)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Reduce verbosity of some libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

    logging.info("Logging system initialized")


# Import RotatingFileHandler
import logging.handlers
