from __future__ import annotations
import json
import pytest
from unittest.mock import MagicMock, patch, call

import lambda_webhook  # import first so module-level `send` binding exists

CHAT_ID = "999"  # matches conftest.py TELEGRAM_CHAT_ID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event(body: dict) -> dict:
    return {"body": json.dumps(body)}


def _msg(text: str, chat_id: str = CHAT_ID) -> dict:
    return _event({"message": {"chat": {"id": int(chat_id)}, "text": text}})


def _callback(chat_id: str = CHAT_ID) -> dict:
    return _event({"callback_query": {"data": "tap", "message": {"chat": {"id": int(chat_id)}}}})


def _invoke(event: dict) -> dict:
    return lambda_webhook.handler(event, MagicMock())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from apex.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def store():
    m = MagicMock()
    m.exists.return_value = True
    m.load.return_value = MagicMock()
    return m


@pytest.fixture()
def repos():
    m = MagicMock()
    m.users.get_state.return_value = ("idle", {})
    return m


@pytest.fixture()
def patched(store, repos):
    """Patch all external collaborators. Returns (store, repos, send, handle, handle_callback)."""
    mock_agent = MagicMock()
    with (
        patch("apex.infra.storage.ProtocolStore", return_value=store),
        patch("apex.infra.db.Repositories", return_value=repos),
        patch("apex.agent.build_agent", return_value=mock_agent) as mock_build,
        patch("apex.handlers.message.handle") as mock_handle,
        patch("apex.handlers.callback.handle_callback") as mock_callback,
        patch("lambda_webhook.send") as mock_send,
    ):
        yield {
            "store": store,
            "repos": repos,
            "agent": mock_agent,
            "build_agent": mock_build,
            "handle": mock_handle,
            "callback": mock_callback,
            "send": mock_send,
        }


# ---------------------------------------------------------------------------
# Security: chat-ID gating
# ---------------------------------------------------------------------------

def test_message_from_wrong_chat_returns_200_silently(patched):
    resp = _invoke(_msg("hello", chat_id="0000"))
    assert resp == {"statusCode": 200}
    patched["handle"].assert_not_called()
    patched["send"].assert_not_called()


def test_callback_from_wrong_chat_returns_200_silently(patched):
    resp = _invoke(_callback(chat_id="0000"))
    assert resp == {"statusCode": 200}
    patched["callback"].assert_not_called()


# ---------------------------------------------------------------------------
# Robustness: malformed / empty payloads
# ---------------------------------------------------------------------------

def test_empty_body_returns_200(patched):
    resp = lambda_webhook.handler({"body": None}, MagicMock())
    assert resp == {"statusCode": 200}


def test_non_text_message_returns_200(patched):
    event = _event({"message": {"chat": {"id": int(CHAT_ID)}}})  # no "text" key
    resp = _invoke(event)
    assert resp == {"statusCode": 200}
    patched["handle"].assert_not_called()


def test_unknown_update_type_returns_200(patched):
    resp = _invoke(_event({"poll": {"id": "abc"}}))
    assert resp == {"statusCode": 200}


# ---------------------------------------------------------------------------
# First-run: no protocol on S3
# ---------------------------------------------------------------------------

def test_no_protocol_non_setup_message_sends_welcome(patched, store):
    store.exists.return_value = False
    resp = _invoke(_msg("hello"))
    assert resp == {"statusCode": 200}
    patched["send"].assert_called_once()
    assert "/setup" in patched["send"].call_args[0][0]


def test_no_protocol_setup_command_proceeds_to_handle(patched, store):
    store.exists.return_value = False
    resp = _invoke(_msg("/setup"))
    assert resp == {"statusCode": 200}
    patched["handle"].assert_called_once()


# ---------------------------------------------------------------------------
# Normal message routing
# ---------------------------------------------------------------------------

def test_valid_message_routes_to_handle_with_agent(patched, repos):
    resp = _invoke(_msg("slept 7 hours"))
    assert resp == {"statusCode": 200}
    patched["handle"].assert_called_once()
    _, kwargs = patched["handle"].call_args
    assert kwargs["agent"] is patched["agent"]
    assert kwargs["text"] == "slept 7 hours"


def test_callback_from_correct_chat_routes_to_handle_callback(patched):
    resp = _invoke(_callback())
    assert resp == {"statusCode": 200}
    patched["callback"].assert_called_once()


# ---------------------------------------------------------------------------
# Resilience: unhandled exceptions must never break the 200 contract
# ---------------------------------------------------------------------------

def test_unhandled_exception_in_handle_still_returns_200(patched):
    patched["handle"].side_effect = RuntimeError("boom")
    resp = _invoke(_msg("hello"))
    assert resp == {"statusCode": 200}


# ---------------------------------------------------------------------------
# C1: store.exists() must be called exactly once per message (not twice)
# ---------------------------------------------------------------------------

def test_store_exists_called_exactly_once_not_twice(patched, store):
    _invoke(_msg("slept 7 hours"))
    assert store.exists.call_count == 1, (
        f"store.exists() called {store.exists.call_count} times — expected 1 (C1 regression)"
    )


# ---------------------------------------------------------------------------
# C2: agent must NOT be built when user sends /setup (wasted work)
# ---------------------------------------------------------------------------

def test_setup_command_does_not_build_agent(patched):
    _invoke(_msg("/setup"))
    patched["build_agent"].assert_not_called()


# ---------------------------------------------------------------------------
# I3: ProtocolStore must NOT be constructed before the chat-ID guard fires
# ---------------------------------------------------------------------------

def test_protocol_store_not_constructed_for_wrong_chat(patched):
    with patch("apex.infra.storage.ProtocolStore") as mock_cls:
        _invoke(_msg("hello", chat_id="0000"))
        mock_cls.assert_not_called()
