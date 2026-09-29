from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SaasSettings(BaseSettings):
    """
    SaaS Core configuration settings.
    All environment variables use the SAAS_ prefix.
    """
    model_config = SettingsConfigDict(
        env_prefix="SAAS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/saas_db",
        description="Database connection string (PostgreSQL/SQLite for tests)"
    )

    # Firebase Authentication
    FIREBASE_PROJECT_ID: Optional[str] = None
    FIREBASE_CLIENT_EMAIL: Optional[str] = None
    FIREBASE_PRIVATE_KEY: Optional[str] = None
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None

    # Cashfree Payments
    BILLING_ENABLED: bool = True
    CASHFREE_CLIENT_ID: Optional[str] = None
    CASHFREE_CLIENT_SECRET: Optional[str] = None
    CASHFREE_ENVIRONMENT: str = "SANDBOX"  # "SANDBOX" or "PRODUCTION"
    CASHFREE_WEBHOOK_SECRET: Optional[str] = None
    CASHFREE_API_VERSION: str = "2023-08-01"

    # Email (Resend)
    EMAIL_ENABLED: bool = True
    RESEND_API_KEY: Optional[str] = None
    RESEND_FROM_EMAIL: str = "onboarding@resend.dev"

    # Cloudflare Turnstile
    TURNSTILE_ENABLED: bool = False
    TURNSTILE_SECRET_KEY: Optional[str] = None

    # Free Trial
    TRIAL_ENABLED: bool = True
    TRIAL_DURATION_DAYS: int = 3
    TRIAL_CREDITS: int = 10

    # Trial Abuse Protection
    TRIAL_HASH_SECRET: str = "default-insecure-trial-secret-change-in-prod"
    TRIAL_IP_LIMIT_ENABLED: bool = True
    TRIAL_IP_MAX_TRIALS: int = 2
    TRIAL_IP_WINDOW_HOURS: int = 24
    TRUSTED_PROXIES: list[str] = []

    # Credit Settings
    CREDIT_DEFAULT_CURRENCY: str = "INR"


_settings: Optional[SaasSettings] = None


def get_saas_settings() -> SaasSettings:
    global _settings
    if _settings is None:
        _settings = SaasSettings()
    return _settings
