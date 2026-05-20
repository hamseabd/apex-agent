from __future__ import annotations
from datetime import date

from strands import tool

from apex.infra.db import Repositories
from apex.infra.storage import ProtocolStore
from apex.infra.telemetry import logger


def build_core_tools(repos: Repositories, store: ProtocolStore) -> list:
    """Return core tool functions closed over repos and store."""

    def get_today_status() -> str:
        """Get a summary of everything logged today."""
        today = date.today().isoformat()
        logs = repos.logs.get_day(today)
        if not logs:
            return "Nothing logged yet today."
        lines = [f"• {l['metric']}: {l['value']}" for l in logs]
        return "Today so far:\n" + "\n".join(lines)

    def get_protocol_summary() -> str:
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

    return [tool(get_today_status), tool(get_protocol_summary)]
