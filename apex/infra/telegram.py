from __future__ import annotations
import json
import logging
import urllib.error
import urllib.request

from apex.settings import get_settings

logger = logging.getLogger(__name__)


def _post(method: str, payload: dict) -> None:
    s = get_settings()
    url = f"https://api.telegram.org/bot{s.telegram_bot_token}/{method}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error(f"Telegram {method} error {e.code}: {body}")
        raise


def send(text: str, parse_mode: str = "HTML") -> None:
    """Send a message to the configured chat."""
    s = get_settings()
    _post("sendMessage", {
        "chat_id": s.telegram_chat_id,
        "text": text,
        "parse_mode": parse_mode,
    })


def send_with_keyboard(text: str, reply_markup: dict) -> None:
    """Send a message with an inline keyboard."""
    s = get_settings()
    _post("sendMessage", {
        "chat_id": s.telegram_chat_id,
        "text": text,
        "reply_markup": reply_markup,
    })


def edit_message(message_id: int, text: str, reply_markup: dict | None = None) -> None:
    """Edit an existing message in place."""
    s = get_settings()
    payload: dict = {
        "chat_id": s.telegram_chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    _post("editMessageText", payload)


def answer_callback(callback_id: str) -> None:
    """Acknowledge a callback query (removes loading spinner)."""
    try:
        _post("answerCallbackQuery", {"callback_query_id": callback_id})
    except Exception:
        pass  # non-critical
