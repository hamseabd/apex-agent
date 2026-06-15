from __future__ import annotations

from strands import tool

from apex.domain.dates import local_today
from apex.domain.models import Metric, Protocol
from apex.tools.core import build_core_tools


def _make_log_tool(metric: Metric, repos, tz_name: str | None = None):
    """Generate a log_<metric> tool for a given metric."""

    def log_fn(value: float, notes: str = "") -> str:
        log_date = local_today(tz_name).isoformat()
        repos.logs.write(metric=metric.name, value=value, log_date=log_date, notes=notes)
        target_str = (
            f" Target: {metric.daily_target}{metric.unit_str}." if metric.daily_target else ""
        )
        return f"Logged {metric.name}: {value}{metric.unit_str}.{target_str}"

    log_fn.__name__ = f"log_{metric.name}"
    log_fn.__doc__ = (
        f"Log {metric.name} in {metric.unit}." if metric.unit else f"Log {metric.name}."
    )
    return tool(log_fn)


def _make_read_tool(metric: Metric, repos, tz_name: str | None = None):
    """Generate a get_<metric>_logs tool for a given metric."""

    def read_fn(days: int = 7) -> str:
        today = local_today(tz_name).isoformat()
        logs = repos.logs.get_range(metric=metric.name, days=days, today=today)
        if not logs:
            return f"No {metric.name} logs in the last {days} days."
        lines = [
            f"• {l['GSI1SK']}: {l['value']}{metric.unit_str}"
            for l in logs
        ]
        return f"{metric.name.title()} (last {days} days):\n" + "\n".join(lines)

    read_fn.__name__ = f"get_{metric.name}_logs"
    read_fn.__doc__ = f"Get {metric.name} history for the last N days."
    return tool(read_fn)


def build_tools(protocol: Protocol, repos, store=None) -> list:
    """
    Generate the agent's complete tool list from the user's protocol.

    Called at Lambda cold start. Each metric in protocol.tracking.metrics
    gets a log_<name> and get_<name>_logs tool. Adding a new metric to the
    protocol creates new tools automatically — no code changes needed.
    """
    tz_name = protocol.profile.timezone
    tools = build_core_tools(repos, store, tz_name) if store else []

    for metric in protocol.tracking.metrics:
        tools.append(_make_log_tool(metric, repos, tz_name))
        tools.append(_make_read_tool(metric, repos, tz_name))

    if protocol.compounds:
        from apex.tools.compound import build_compound_tools
        tools.extend(build_compound_tools(protocol.compounds, repos, store, tz_name))

    return tools
