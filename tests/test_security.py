"""Security regression tests — one test per identified vulnerability."""
import json
from unittest.mock import MagicMock

import pytest


# ── Fix 1: HTML injection in _send_summary ──────────────────────────────────


def test_send_summary_escapes_html_in_goal(monkeypatch):
    from apex.handlers.setup import _send_summary

    captured = []
    monkeypatch.setattr("apex.handlers.setup.send", lambda t: captured.append(t))
    _send_summary({"goal": "<b>fat loss</b> & gain", "metrics": [], "schedule": {}})
    text = captured[0]
    # The template has intentional <b> tags; check the user-supplied ones are escaped
    assert "<b>fat loss</b>" not in text, "user-supplied <b> must be escaped, not rendered"
    assert "&lt;b&gt;fat loss&lt;/b&gt;" in text
    assert "&amp;" in text


def test_send_summary_escapes_html_in_metric_names(monkeypatch):
    from apex.handlers.setup import _send_summary

    captured = []
    monkeypatch.setattr("apex.handlers.setup.send", lambda t: captured.append(t))
    _send_summary({"goal": "lean out", "metrics": ["<em>sleep</em>", "protein"], "schedule": {}})
    text = captured[0]
    assert "<em>" not in text, "raw <em> tag in metric name must be escaped"
    assert "&lt;em&gt;" in text


def test_send_summary_escapes_html_in_compound_names(monkeypatch):
    from apex.handlers.setup import _send_summary

    captured = []
    monkeypatch.setattr("apex.handlers.setup.send", lambda t: captured.append(t))
    _send_summary({
        "goal": "lean out",
        "metrics": [],
        "schedule": {},
        "compounds": [{"name": "<a href='http://evil.com'>BPC-157</a>"}],
    })
    text = captured[0]
    assert "<a href" not in text, "raw <a> tag in compound name must be escaped"
    assert "&lt;a" in text


# ── Fix 2: _apply_edit strips unknown protocol keys ──────────────────────────


def test_apply_edit_strips_unknown_protocol_keys(monkeypatch):
    from apex.handlers.setup import _apply_edit

    monkeypatch.setattr(
        "apex.handlers.setup._call_llm",
        lambda system_prompt, user_message: json.dumps({
            "updated_protocol": {"goal": "lose fat", "inject": "malicious_value"},
            "reply": "Updated.",
        }),
    )
    repos = MagicMock()
    monkeypatch.setattr("apex.handlers.setup.send", lambda t: None)
    monkeypatch.setattr("apex.handlers.setup._send_summary", lambda p: None)

    _apply_edit("change goal to lose fat", {"protocol": {"goal": "old goal"}}, repos)

    assert repos.users.set_state.called, "set_state should be called for valid update"
    stored_context = repos.users.set_state.call_args[0][1]
    assert "inject" not in stored_context["protocol"], "unknown key must be stripped"
    assert stored_context["protocol"]["goal"] == "lose fat"


def test_apply_edit_rejects_non_dict_updated_protocol(monkeypatch):
    from apex.handlers.setup import _apply_edit

    monkeypatch.setattr(
        "apex.handlers.setup._call_llm",
        lambda system_prompt, user_message: json.dumps({
            "updated_protocol": ["hacked", "list"],
            "reply": "hacked",
        }),
    )
    repos = MagicMock()
    monkeypatch.setattr("apex.handlers.setup.send", lambda t: None)

    _apply_edit("change goal", {"protocol": {"goal": "old"}}, repos)

    repos.users.set_state.assert_not_called()


# ── Fix 3: size limit on extracted data before DynamoDB storage ──────────────

_HUGE_EXTRACTED = {"metrics": ["x" * 5000] * 20}  # ~100 KB


def test_handle_setup_message_rejects_oversized_extracted_data(monkeypatch):
    from apex.handlers.setup import handle_setup_message

    monkeypatch.setattr(
        "apex.handlers.setup._ask_claude",
        lambda *a, **kw: json.dumps({
            "reply": "Got it.",
            "extracted": _HUGE_EXTRACTED,
            "advance": True,
        }),
    )
    repos = MagicMock()
    monkeypatch.setattr("apex.handlers.setup.send", lambda t: None)

    handle_setup_message("I want to track sleep", "metrics", {"protocol": {}}, repos)

    for call in repos.users.set_state.call_args_list:
        ctx = call[0][1]  # second positional arg is the context dict
        size = len(json.dumps(ctx).encode())
        assert size < 100_000, f"oversized context ({size} bytes) must not be stored"


# ── Fix 4: send_with_keyboard must include parse_mode ────────────────────────


def test_send_with_keyboard_includes_parse_mode(monkeypatch):
    from apex.infra import telegram

    posted = []
    monkeypatch.setattr(telegram, "_post", lambda method, payload: posted.append(payload))
    telegram.send_with_keyboard("Hello <b>World</b>", {"inline_keyboard": []})

    assert posted, "_post was not called"
    assert "parse_mode" in posted[0], "send_with_keyboard must include parse_mode in payload"
    assert posted[0]["parse_mode"] == "HTML"


# ── Fix 5: _deep_update preserves extra YAML keys not in the model ───────────


def test_deep_update_preserves_extra_yaml_keys():
    from ruamel.yaml.comments import CommentedMap
    from apex.infra.storage import _deep_update

    target = CommentedMap({"name": "Alex", "custom_note": "keep me"})
    source = {"name": "Bob"}
    _deep_update(target, source)

    assert "custom_note" in target, "key absent from source must be preserved in CommentedMap"
    assert target["name"] == "Bob", "key present in source must be updated"
