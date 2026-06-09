from __future__ import annotations
from apex.infra.telemetry import logger
from apex.infra.telegram import send


def _load_protocol_safe():
    try:
        from apex.infra.storage import ProtocolStore
        store = ProtocolStore()
        return store.load() if store.exists() else None
    except Exception:
        return None


def _current_utc_hour() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%H:")


def morning_checkin() -> None:
    send(
        "☀️ <b>Good morning!</b>\n\n"
        "How did you sleep? Just tell me naturally — "
        "I'll log it and anything else you mention."
    )


def run_reminders() -> None:
    protocol = _load_protocol_safe()
    if not protocol:
        return
    current_hour = _current_utc_hour()
    for reminder in protocol.schedule.reminders:
        if reminder.time.startswith(current_hour):
            fn = _REGISTRY.get(reminder.job)
            if fn:
                fn()


def water_reminder() -> None:
    protocol = _load_protocol_safe()
    target = protocol.tracking.get_target("water") if protocol else None
    target_str = f" Target: {int(target)}oz." if target else ""
    send(f"💧 Water check — how much have you had today?{target_str}")


def bedtime_prompt() -> None:
    send(
        "🌙 Wind down time.\n\n"
        "Log anything from today you haven't logged yet — "
        "just tell me and I'll handle it."
    )


def missed_day_check() -> None:
    from apex.infra.db import Repositories
    from datetime import date
    repos = Repositories()
    today = date.today().isoformat()
    logs = repos.logs.get_day(today)
    if not logs:
        send(
            "👀 Haven't heard from you today.\n\n"
            "How's it going? Log anything — sleep last night, meals, workout."
        )


def weekly_summary() -> None:
    from apex.infra.db import Repositories
    protocol = _load_protocol_safe()
    if not protocol:
        return
    repos = Repositories()
    lines = ["📊 <b>Week in review</b>\n"]
    for metric in protocol.tracking.metrics:
        logs = repos.logs.get_range(metric=metric.name, days=7)
        if not logs:
            lines.append(f"• {metric.name}: no data this week")
            continue
        values = [l["value"] for l in logs]
        avg = sum(values) / len(values)
        target_str = f" / {metric.daily_target}{metric.unit_str}" if metric.daily_target else ""
        lines.append(
            f"• {metric.name}: avg {avg:.1f}{metric.unit_str}{target_str} ({len(logs)}/7 days logged)"
        )
    send("\n".join(lines))


_REGISTRY = {
    "morning_checkin": morning_checkin,
    "run_reminders": run_reminders,
    "water_reminder": water_reminder,
    "bedtime_prompt": bedtime_prompt,
    "missed_day_check": missed_day_check,
    "weekly_summary": weekly_summary,
}


def run(job: str) -> None:
    fn = _REGISTRY.get(job)
    if fn:
        logger.info(f"Running job: {job}")
        fn()
    else:
        logger.warning(f"Unknown job: {job}")
