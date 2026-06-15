from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_chat_id: str
    # Optional shared secret for Telegram webhook validation. When set, incoming
    # requests must carry a matching X-Telegram-Bot-Api-Secret-Token header
    # (register it via setWebhook's secret_token parameter).
    telegram_webhook_secret: str = ""
    aws_region: str = "us-east-1"
    config_bucket: str
    table_name: str = "apex"

    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-6"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg] — required fields come from env vars
