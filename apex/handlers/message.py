from __future__ import annotations

from strands import Agent

from apex.infra.db import Repositories
from apex.infra.telemetry import logger, tracer
from apex.infra.telegram import send


@tracer.capture_method
def handle(text: str, agent: Agent | None, repos: Repositories) -> None:
    """Route an incoming text message."""
    state, context = repos.users.get_state()

    if state == "setup_in_progress":
        from apex.handlers.setup import handle_setup_message
        handle_setup_message(
            text=text,
            step=context.get("step", "goal"),
            context=context,
            repos=repos,
        )
        return

    if text.strip() == "/setup":
        from apex.handlers.setup import handle_setup_start
        handle_setup_start(repos=repos)
        return

    if agent is None:
        send("Protocol not configured. Send /setup to get started.")
        return

    logger.info("Routing to agent", extra={"preview": text[:60]})
    response = str(agent(text))
    send(response)
