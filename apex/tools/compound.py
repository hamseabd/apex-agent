from __future__ import annotations
from strands import tool

from apex.domain.compound import CompoundCycle
from apex.domain.dates import local_today, protocol_today


def build_compound_tools(compounds: list, repos, store=None, tz_name: str | None = None) -> list:
    """Build compound tools from protocol.compounds list."""
    cycle_objs = [CompoundCycle.from_protocol(c.model_dump()) for c in compounds]
    return [
        _make_get_compound_status(cycle_objs, tz_name),
        _make_activate_compound(cycle_objs, store),
    ]


def _make_get_compound_status(compounds: list[CompoundCycle], tz_name: str | None = None):
    def get_compound_status() -> str:
        """Get current cycle status, dosing, and days remaining for all compounds."""
        today = local_today(tz_name)
        if not compounds:
            return "No compounds configured."
        lines = []
        for c in compounds:
            s = c.get_status(today)
            status = s["status"]
            if status == "not_started":
                lines.append(f"{c.name}: not started — send '{c.name} arrived' to activate")
                continue
            dose = c.get_current_dose(today)
            dose_str = " · ".join(f"{k}: {v}" for k, v in dose.items() if k not in ("days",))
            icon = "🟢" if status == "on" else "🔴"
            lines.append(
                f"{icon} {c.name}: {status.upper()} day {s['current_day']} "
                f"— {dose_str} — {s['days_remaining']}d until next transition"
            )
        return "\n".join(lines)

    get_compound_status.__name__ = "get_compound_status"
    return tool(get_compound_status)


def _make_activate_compound(compounds: list[CompoundCycle], store):
    def activate_compound(name: str) -> str:
        """Activate a compound by name — sets its start_date to today."""
        if store is None:
            return "Error: protocol store unavailable — cannot activate compounds."
        protocol = store.load()
        compound_list = protocol.compounds or []
        matched = None
        for c in compound_list:
            if c.name.lower() == name.lower():
                c.start_date = protocol_today(protocol).isoformat()
                matched = c
                break
        if matched is None:
            names = ", ".join(c.name for c in compound_list)
            return f"Compound '{name}' not found. Configured: {names}"
        updated = protocol.model_copy(update={"compounds": compound_list})
        store.save(updated)
        return f"✅ {matched.name} activated. Cycle started today."

    activate_compound.__name__ = "activate_compound"
    return tool(activate_compound)
