"""
Tests that bedrock_model_id from Settings flows through to setup.py and agent.py.
"""
from __future__ import annotations
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# setup.py — _call_llm must use the model_id from settings, not a hardcoded string
# ---------------------------------------------------------------------------

def test_call_llm_uses_model_id_from_settings(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "eu.anthropic.claude-opus-4-7")

    from apex.settings import get_settings
    get_settings.cache_clear()

    mock_client = MagicMock()
    mock_client.converse.return_value = {
        "output": {"message": {"content": [{"text": '{"reply": "hi", "extracted": null, "advance": false}'}]}}
    }

    with patch("apex.handlers.setup._bedrock_client", return_value=mock_client):
        from apex.handlers.setup import _call_llm
        _call_llm(system_prompt="test", user_message="hello")

    call_kwargs = mock_client.converse.call_args
    assert call_kwargs.kwargs["modelId"] == "eu.anthropic.claude-opus-4-7", (
        "_call_llm should use settings.bedrock_model_id, not a hardcoded string"
    )

    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# agent.py — build_agent must pass model_id from settings to BedrockModel
# ---------------------------------------------------------------------------

def test_build_agent_uses_model_id_from_settings(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "eu.anthropic.claude-opus-4-7")

    from apex.settings import get_settings
    get_settings.cache_clear()

    mock_protocol = MagicMock()
    mock_repos = MagicMock()
    mock_store = MagicMock()

    with (
        patch("apex.tools.factory.build_tools", return_value=[]),
        patch("apex.agent.BedrockModel") as mock_bedrock_cls,
        patch("apex.agent.Agent"),
    ):
        from apex.agent import build_agent
        build_agent(mock_protocol, mock_repos, mock_store)

    mock_bedrock_cls.assert_called_once()
    _, kwargs = mock_bedrock_cls.call_args
    assert kwargs.get("model_id") == "eu.anthropic.claude-opus-4-7", (
        "build_agent should pass settings.bedrock_model_id to BedrockModel"
    )

    get_settings.cache_clear()
