from __future__ import annotations
from strands import tool
from apex.infra.telemetry import logger


@tool
def get_today_status(repos) -> str:
    """Get a summary of everything logged today."""
    from datetime import date
    today = date.today().isoformat()
    logs = repos.logs.get_day(today)
    if not logs:
        return "Nothing logged yet today."
    lines = [
        f"• {l['metric']}: {l['value']}"
        for l in logs
    ]
    return "Today so far:\n" + "\n".join(lines)


@tool
def get_protocol_summary(store) -> str:
    """Get the user's current protocol — what metrics they track and their targets."""
    try:
        protocol = store.load()
        lines = []
        for m in protocol.tracking.metrics:
            target_str = f" (target: {m.daily_target}{m.unit_str})" if m.daily_target else ""
            lines.append(f"• {m.name}{m.unit_str}{target_str}")
        return f"Your protocol v{protocol.version} — tracking:\n" + "\n".join(lines)
    except Exception as e:
        logger.error(f"Failed to load protocol: {e}")
        return "Could not load protocol."


CORE_TOOLS = [get_today_status, get_protocol_summary]
