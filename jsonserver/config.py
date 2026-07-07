"""
Configuration module for JSONServer.
Handles environment variables and default settings.
"""

import os
import secrets


class Config:
    """Base configuration with sensible defaults."""

    # Database storage path
    DB_PATH: str = os.environ.get("JSONSERVER_DB_PATH", "data")

    # Authentication
    API_KEYS: list[str] = [
        k.strip()
        for k in os.environ.get("JSONSERVER_API_KEYS", "").split(",")
        if k.strip()
    ]
    # If no keys set via env, generate one on startup (printed to console)
    REQUIRE_AUTH: bool = os.environ.get("JSONSERVER_REQUIRE_AUTH", "true").lower() == "true"

    # Rate limiting (requests per minute per IP)
    RATE_LIMIT: int = int(os.environ.get("JSONSERVER_RATE_LIMIT", "120"))

    # Security
    MAX_PAYLOAD_SIZE: int = int(os.environ.get("JSONSERVER_MAX_PAYLOAD", str(1024 * 1024)))  # 1MB
    MAX_RECORDS_PER_REQUEST: int = int(os.environ.get("JSONSERVER_MAX_RECORDS", "1000"))
    MAX_FIELD_LENGTH: int = int(os.environ.get("JSONSERVER_MAX_FIELD_LEN", "10000"))

    # Server
    HOST: str = os.environ.get("JSONSERVER_HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("JSONSERVER_PORT", "5000"))
    DEBUG: bool = os.environ.get("JSONSERVER_DEBUG", "false").lower() == "true"

    # CORS
    CORS_ORIGINS: str = os.environ.get("JSONSERVER_CORS_ORIGINS", "*")


class ProductionConfig(Config):
    """Production configuration — strict security."""
    DEBUG = False
    REQUIRE_AUTH = True


class DevelopmentConfig(Config):
    """Development configuration — relaxed security."""
    DEBUG = True
    REQUIRE_AUTH = False
    RATE_LIMIT = 1000


class TestingConfig(Config):
    """Testing configuration — isolated environment."""
    DEBUG = True
    REQUIRE_AUTH = False
    DB_PATH = "test_data"
    RATE_LIMIT = 10000


# Map environment names to config classes
CONFIGS = {
    "production": ProductionConfig,
    "development": DevelopmentConfig,
    "testing": TestingConfig,
}


def get_config() -> Config:
    """Return the active configuration based on JSONSERVER_ENV."""
    env = os.environ.get("JSONSERVER_ENV", "development").lower()
    config_class = CONFIGS.get(env, DevelopmentConfig)
    return config_class()
