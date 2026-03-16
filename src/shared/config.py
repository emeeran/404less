"""
Centralized configuration with validation.

Ensures required secrets are set in production environments.

@spec Shared infrastructure - configuration management
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Application Constants
# ============================================================================

APP_NAME = "404less"
APP_VERSION = "0.1.0"
DEFAULT_USER_AGENT = f"{APP_NAME}/{APP_VERSION} (+https://github.com/user/404less)"

# ============================================================================
# Crawler Configuration (with environment overrides)
# ============================================================================

CRAWLER_MAX_CONCURRENT = int(os.environ.get("CRAWLER_MAX_CONCURRENT", "5"))
CRAWLER_MIN_DELAY = float(os.environ.get("CRAWLER_MIN_DELAY", "0.1"))
CRAWLER_TIMEOUT = int(os.environ.get("CRAWLER_TIMEOUT", "30"))
CRAWLER_MAX_REDIRECTS = int(os.environ.get("CRAWLER_MAX_REDIRECTS", "10"))
CRAWLER_MAX_DEPTH = int(os.environ.get("CRAWLER_MAX_DEPTH", "10"))


class ConfigError(Exception):
    """Raised when configuration is invalid or missing required values."""

    pass


def _get_required_env(name: str) -> str:
    """
    Get required environment variable.

    Raises:
        ConfigError: If the variable is not set.
    """
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Required environment variable {name} is not set")
    return value


def _is_production() -> bool:
    """Check if running in production environment."""
    return os.environ.get("ENVIRONMENT", "development").lower() == "production"


# ============================================================================
# Environment
# ============================================================================

ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

# ============================================================================
# JWT Configuration - NO DEFAULT in production
# ============================================================================

JWT_SECRET_KEY: str
if _is_production():
    JWT_SECRET_KEY = _get_required_env("JWT_SECRET_KEY")
else:
    JWT_SECRET_KEY = os.environ.get(
        "JWT_SECRET_KEY", "dev-secret-key-DO-NOT-USE-IN-PRODUCTION"
    )
    if "DO-NOT-USE-IN-PRODUCTION" not in JWT_SECRET_KEY:
        logger.warning(
            "Using development JWT secret. Set JWT_SECRET_KEY for production."
        )

JWT_ALGORITHM = "HS256"

# ============================================================================
# Database Configuration
# ============================================================================

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./sdd.db")
DB_REQUIRED = os.environ.get("DB_REQUIRED", "false").lower() == "true"
SQL_ECHO = os.environ.get("SQL_ECHO", "false").lower() == "true"

# ============================================================================
# Email Configuration
# ============================================================================

EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "console")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "noreply@example.com")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
