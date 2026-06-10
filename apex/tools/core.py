from __future__ import annotations
from datetime import date
from typing import Any

from strands import tool

from apex.infra.db import Repositories
from apex.infra.storage import ProtocolStore
from apex.infra.telemetry import logger


def _format_log_line(log: dict, metric) -> str:
    """One status line per log — progress bar when the metric has a daily target."""
    name = log["metric"]
    value = log["value"]
    if metric is None or not metric.daily_target or not isinstance(value, (int, float)):
        return f"• {name}: {value}"
    pct = value / metric.daily_target
    filled = min(10, round(pct * 10))
    bar = "█" * filled + "░" * (10 - filled)
    target = metric.daily_target
    target_str = int(target) if target == int(target) else target
    return f"• {name}: {bar} {value}/{target_str}{metric.unit_str} ({pct:.0%})"


def build_core_tools(repos: Repositories, store: ProtocolStore) -> list:
    """Return core tool functions closed over repos and store."""

    def get_today_status() -> str:
        """Get a summary of everything logged today, with progress toward daily targets."""
        today = date.today().isoformat()
        logs = repos.logs.get_day(today)
        if not logs:
            return "Nothing logged yet today."

        try:
            metrics = {m.name: m for m in store.load().tracking.metrics}
        except Exception:
            metrics = {}

        grouped: dict[str, list[str]] = {}
        for l in logs:
            metric = metrics.get(l["metric"])
            grouped.setdefault(
                metric.category if metric and metric.category else "other", []
            ).append(_format_log_line(l, metric))

        if list(grouped) == ["other"]:
            return "Today so far:\n" + "\n".join(grouped["other"])
        sections = []
        for category, lines in grouped.items():
            sections.append(f"<b>{category.title()}</b>\n" + "\n".join(lines))
        return "Today so far:\n\n" + "\n\n".join(sections)

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

    def update_protocol(field_path: str, value: str) -> str:
        """
        Update a field in the user's health protocol using dot notation.
        field_path examples: 'profile.goal', 'schedule.morning_checkin', 'tracking.metrics.0.daily_target'
        value is always passed as a string and cast to match the existing field type.
        """
        try:
            protocol = store.load()
        except Exception:
            return "Error: could not load protocol."
        data = protocol.model_dump()
        keys = field_path.split(".")
        current: Any = data
        for key in keys[:-1]:
            try:
                current = current[int(key)] if isinstance(current, list) else current[key]
            except (KeyError, IndexError, TypeError):
                return f"Error: '{field_path}' not found in protocol."
        final_key = keys[-1]
        try:
            existing_container = current
            existing = current[int(final_key)] if isinstance(current, list) else current[final_key]
        except (KeyError, IndexError, TypeError):
            return f"Error: field '{final_key}' not found."
        typed_key: Any = int(final_key) if isinstance(current, list) else final_key
        try:
            if isinstance(existing, int):
                current[typed_key] = int(value)
            elif isinstance(existing, float):
                current[typed_key] = float(value)
            else:
                current[typed_key] = value
        except (ValueError, TypeError):
            current[typed_key] = value
        try:
            from apex.domain.models import Protocol as ProtocolModel
            store.save(ProtocolModel(**data))
        except Exception as e:
            return f"Error: could not save protocol — {e}"
        return f"✅ Updated {field_path} → {current[typed_key]}."

    return [tool(get_today_status), tool(get_protocol_summary), tool(update_protocol)]
