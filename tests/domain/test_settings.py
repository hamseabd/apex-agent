import pytest


def test_settings_reads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "456")
    monkeypatch.setenv("CONFIG_BUCKET", "my-bucket")
    monkeypatch.setenv("TABLE_NAME", "apex-test")

    from apex.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()

    assert s.telegram_bot_token == "123:abc"
    assert s.telegram_chat_id == "456"
    assert s.config_bucket == "my-bucket"
    assert s.aws_region == "us-east-1"


def test_settings_bedrock_model_id_defaults_to_sonnet(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "456")
    monkeypatch.setenv("CONFIG_BUCKET", "my-bucket")
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)

    from apex.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()

    assert s.bedrock_model_id == "us.anthropic.claude-sonnet-4-6"


def test_settings_bedrock_model_id_reads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "456")
    monkeypatch.setenv("CONFIG_BUCKET", "my-bucket")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "eu.anthropic.claude-opus-4-7")

    from apex.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()

    assert s.bedrock_model_id == "eu.anthropic.claude-opus-4-7"


def test_settings_missing_required_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("CONFIG_BUCKET", raising=False)
    from apex.settings import get_settings
    get_settings.cache_clear()
    with pytest.raises(Exception):
        get_settings()
