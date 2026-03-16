"""
Centralized configuration with validation.

Ensures required secrets are set in production environments.

@spec Shared infrastructure - configuration management
"""

import os
import logging
import secrets
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


def _validate_production_config() -> None:
    """
    Validate that all required production configuration is present.

    Raises:
        ConfigError: If any required configuration is missing or invalid.
    """
    if not _is_production():
        return

    errors = []

    # JWT secret must be set and secure
    jwt_secret = os.environ.get("JWT_SECRET_KEY", "")
    if not jwt_secret:
        errors.append("JWT_SECRET_KEY is required in production")
    elif "DO-NOT-USE-IN-PRODUCTION" in jwt_secret:
        errors.append("JWT_SECRET_KEY contains development placeholder")
    elif len(jwt_secret) < 32:
        errors.append("JWT_SECRET_KEY must be at least 32 characters")

    # Database URL must be PostgreSQL in production
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        errors.append("DATABASE_URL is required in production")
    elif not database_url.startswith(("postgresql://", "postgresql+asyncpg://")):
        logger.warning(
            "DATABASE_URL should use PostgreSQL in production for reliability"
        )

    # Email must be configured for user features
    email_backend = os.environ.get("EMAIL_BACKEND", "console")
    if email_backend == "smtp":
        if not os.environ.get("SMTP_HOST"):
            errors.append("SMTP_HOST is required when EMAIL_BACKEND=smtp")
        if not os.environ.get("SMTP_PASSWORD"):
            errors.append("SMTP_PASSWORD is required when EMAIL_BACKEND=smtp")

    # BASE_URL must be set for email links
    base_url = os.environ.get("BASE_URL", "")
    if not base_url or "localhost" in base_url:
        errors.append("BASE_URL must be set to production URL (not localhost)")

    if errors:
        error_msg = "Production configuration errors:\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        raise ConfigError(error_msg)

    logger.info("Production configuration validated successfully")


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

# Database connection pool settings
DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW = int(os.environ.get("DB_MAX_OVERFLOW", "20"))
DB_POOL_TIMEOUT = int(os.environ.get("DB_POOL_TIMEOUT", "30"))
DB_POOL_RECYCLE = int(os.environ.get("DB_POOL_RECYCLE", "3600"))

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

# ============================================================================
# Rate Limiting Configuration
# ============================================================================

RATE_LIMIT_SCAN_CREATE = os.environ.get("RATE_LIMIT_SCAN_CREATE", "10/hour")
RATE_LIMIT_LOGIN = os.environ.get("RATE_LIMIT_LOGIN", "20/minute")
RATE_LIMIT_REGISTER = os.environ.get("RATE_LIMIT_REGISTER", "5/hour")
RATE_LIMIT_PASSWORD_RESET = os.environ.get("RATE_LIMIT_PASSWORD_RESET", "3/hour")


def validate_config() -> None:
    """
    Validate configuration at application startup.

    Call this function during application initialization to fail fast
    on missing or invalid configuration.
    """
    _validate_production_config()
    logger.info("Configuration validated for %s environment", ENVIRONMENT)
