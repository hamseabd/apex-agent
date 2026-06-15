from __future__ import annotations
import json

from aws_lambda_powertools.utilities.typing import LambdaContext

from apex.infra.telemetry import logger, tracer, metrics
from apex.infra.telegram import send
from apex.settings import get_settings


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=False)
@metrics.log_metrics
def handler(event: dict, context: LambdaContext) -> dict:
    try:
        s = get_settings()

        # Telegram webhook secret — rejects forged requests to the public URL.
        if s.telegram_webhook_secret:
            headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
            if headers.get("x-telegram-bot-api-secret-token") != s.telegram_webhook_secret:
                logger.warning("Webhook secret mismatch — rejecting request")
                return {"statusCode": 403}

        body = json.loads(event.get("body") or "{}")

        # Inline keyboard callback
        if cq := body.get("callback_query"):
            if str(cq["message"]["chat"]["id"]) == s.telegram_chat_id:
                from apex.handlers.callback import handle_callback
                from apex.infra.db import Repositories
                from apex.infra.storage import ProtocolStore
                handle_callback(cq, repos=Repositories(), store=ProtocolStore())
            return {"statusCode": 200}

        message = body.get("message") or body.get("edited_message")
        if not message:
            return {"statusCode": 200}

        chat_id = str(message["chat"]["id"])
        text = message.get("text", "").strip()

        if not text or chat_id != s.telegram_chat_id:
            return {"statusCode": 200}

        logger.info("Message received", extra={"preview": text[:60]})

        # Redirect to /setup if protocol not yet created
        from apex.infra.storage import ProtocolStore
        store = ProtocolStore()
        protocol_exists = store.exists()

        if text != "/setup" and not protocol_exists:
            send("👋 Welcome to Apex! Send /setup to configure your personal protocol.")
            return {"statusCode": 200}

        from apex.infra.db import Repositories
        repos = Repositories()

        agent = None
        protocol = None
        state, _ = repos.users.get_state()
        if protocol_exists and text != "/setup" and state != "setup_in_progress":
            protocol = store.load()
            from apex.agent import build_agent
            agent = build_agent(protocol, repos, store)

        from apex.handlers.message import handle
        handle(text=text, agent=agent, repos=repos, store=store, protocol=protocol)

    except Exception:
        logger.exception("Unhandled webhook error")

    return {"statusCode": 200}
