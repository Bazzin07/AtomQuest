from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AtomQuest API"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://atomquest:atomquest@localhost:5432/atomquest"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = Field(default="change-me-before-deploying", min_length=16)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    auto_create_tables: bool = False
    demo_mode: bool = False
    frontend_app_url: str = "http://localhost:5173"

    # CORS — comma-separated list of allowed origins. Use "*" for dev only.
    # Example: "https://app.atomquest.io,https://admin.atomquest.io"
    allowed_origins: str = "*"

    # Redis session cache TTL in seconds (15 min default).
    session_ttl_seconds: int = 900

    # Redis token blacklist TTL — match token lifetime so blacklisted tokens
    # expire naturally from Redis alongside the JWT expiry.
    token_blacklist_ttl_seconds: int = 3600

    # Toggle Redis-backed rate limiting (disable in unit test environments)
    rate_limit_enabled: bool = True

    # ── Email (SMTP) ──────────────────────────────────────────────────────────
    # Set notifications_enabled=true and provide SMTP credentials to activate.
    # Works with any SMTP provider: Gmail, Resend SMTP, AWS SES SMTP relay, etc.
    notifications_enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@atomquest.io"
    smtp_use_tls: bool = True

    # ── Microsoft Entra ID SSO ────────────────────────────────────────────────
    microsoft_tenant_id: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = ""

    # ── Microsoft Teams Webhook ───────────────────────────────────────────────
    # Incoming Webhook URL from a Teams channel connector.
    # Leave empty to disable Teams notifications.
    teams_webhook_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins(self) -> list[str]:
        """Return allowed origins as a list."""
        if self.allowed_origins == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def email_enabled(self) -> bool:
        """True only when notifications are enabled AND SMTP credentials present."""
        return self.notifications_enabled and bool(self.smtp_user) and bool(self.smtp_password)

    @property
    def teams_enabled(self) -> bool:
        """True only when Teams webhook URL is configured."""
        return self.notifications_enabled and bool(self.teams_webhook_url)

    @property
    def password_auth_enabled(self) -> bool:
        return True

    @property
    def microsoft_sso_enabled(self) -> bool:
        return all(
            [
                self.microsoft_tenant_id,
                self.microsoft_client_id,
                self.microsoft_client_secret,
                self.microsoft_redirect_uri,
            ]
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
