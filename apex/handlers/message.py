from __future__ import annotations

from strands import Agent

from apex.domain.compound import CompoundCycle, matches_compound_name
from apex.domain.dates import protocol_today
from apex.infra.db import Repositories
from apex.infra.telemetry import logger, tracer
from apex.infra.telegram import send


@tracer.capture_method
def handle(text: str, agent: Agent | None, repos: Repositories, store=None, protocol=None) -> None:
    """Route an incoming text message. Pass `protocol` if already loaded to skip a re-fetch."""
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

    if protocol is None and store and store.exists():
        protocol = store.load()
    if protocol is not None and store and _is_compound_arrival(text, protocol):
        _handle_compound_arrival(text, protocol, store)
        return

    if agent is None:
        send("Protocol not configured. Send /setup to get started.")
        return

    logger.info("Routing to agent", extra={"preview": text[:60]})
    response = str(agent(text))
    send(response)


def _is_compound_arrival(text: str, protocol) -> bool:
    """Check if text looks like '[compound name] arrived'."""
    if not protocol or not protocol.compounds:
        return False
    text_lower = text.lower().strip()
    if not text_lower.endswith("arrived"):
        return False
    prefix = text_lower.replace("arrived", "").strip().rstrip(",").strip()
    if prefix in ("all", "compounds"):
        return True
    return any(matches_compound_name(prefix, c.name) for c in protocol.compounds)


def _handle_compound_arrival(text: str, protocol, store) -> None:
    from apex.infra.telegram import send
    today = protocol_today(protocol)
    text_lower = text.lower().replace("arrived", "").strip()
    compound_list = list(protocol.compounds or [])
    activated = []
    for c in compound_list:
        if matches_compound_name(text_lower, c.name) or text_lower in ("all", "compounds"):
            c.start_date = today.isoformat()
            activated.append(c)
    if not activated:
        send("Couldn't match that to any compound in your protocol.")
        return
    updated = protocol.model_copy(update={"compounds": compound_list})
    store.save(updated)
    lines = []
    for c in activated:
        cc = CompoundCycle.from_protocol(c.model_dump())
        dose = cc.get_current_dose(today=today)
        dose_str = " · ".join(f"{k}: {v}" for k, v in dose.items() if k != "days")
        intro_note = " (intro stage active)" if cc.intro else ""
        lines.append(f"• {c.name}: ON{intro_note} — {dose_str}")
    send(
        f"💉 <b>{'Compound' if len(activated) == 1 else 'Compounds'} activated!</b>\n\n"
        + "\n".join(lines)
        + "\n\nI'll remind you tonight."
    )
