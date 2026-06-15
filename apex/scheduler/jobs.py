from __future__ import annotations
from apex.domain.compound import CompoundCycle
from apex.domain.dates import protocol_today
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
    protocol = _load_protocol_safe()
    send(
        "☀️ <b>Good morning!</b>\n\n"
        "How did you sleep? Just tell me naturally — "
        "I'll log it and anything else you mention."
    )

    # If supplements configured, send keyboard follow-up
    if protocol and protocol.supplements and protocol.supplements.morning:
        from apex.infra.keyboards import supplement_check_keyboard
        from apex.infra.telegram import send_with_keyboard
        send_with_keyboard("💊 Yesterday's supplements?", supplement_check_keyboard())


def run_reminders() -> None:
    protocol = _load_protocol_safe()
    if not protocol:
        return
    current_hour = _current_utc_hour()
    for reminder in protocol.schedule.reminders:
        # zfill normalizes "9:00" → "09:00" so non-padded times still match
        if reminder.time.strip().zfill(5).startswith(current_hour):
            fn = _REMINDER_SAFE_JOBS.get(reminder.job)
            if fn:
                fn()
            else:
                logger.warning(f"Reminder job not reminder-safe, skipping: {reminder.job}")


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


def morning_injection_reminder() -> None:
    """AM dose reminder for compounds with am dosing."""
    protocol = _load_protocol_safe()
    if not protocol or not protocol.compounds:
        return
    today = protocol_today(protocol)
    lines = []
    for entry in protocol.compounds:
        c = CompoundCycle.from_protocol(entry.model_dump())
        if c.get_status(today)["status"] != "on":
            continue
        dose = c.get_current_dose(today)
        am = dose.get("am")
        if not am:
            continue
        days_setting = dose.get("days", "daily")
        if days_setting == "weekdays" and today.weekday() >= 5:
            continue
        lines.append(f"• {c.name}: {am}")
    if lines:
        send("🌅 Morning injections:\n\n" + "\n".join(lines))


def injection_reminder() -> None:
    """PM dose reminder with dose escalation alerts."""
    protocol = _load_protocol_safe()
    if not protocol or not protocol.compounds:
        return
    today = protocol_today(protocol)
    lines = []
    alerts = []
    for entry in protocol.compounds:
        c = CompoundCycle.from_protocol(entry.model_dump())
        status = c.get_status(today)
        if status["status"] != "on":
            continue
        dose = c.get_current_dose(today)
        pm = dose.get("pm")
        if not pm:
            continue
        # Check for escalation tonight
        if c.start_date:
            day = (today - c.start_date).days + 1
            for stage in c.intro:
                from_day = stage.get("from_day")
                if from_day and day == from_day:
                    dose_str = " · ".join(
                        f"{k}: {v}" for k, v in stage.items()
                        if k not in ("from_day", "through_day")
                    )
                    alerts.append(f"⚠️ {c.name} dose change tonight: {dose_str}")
        lines.append(f"• {c.name}: {pm} (day {status['current_day']})")
    if not lines:
        return
    msg = ""
    if alerts:
        msg += "\n".join(alerts) + "\n\n"
    msg += "💉 Evening injections:\n\n" + "\n".join(lines)
    from apex.infra.keyboards import compound_check_keyboard
    from apex.infra.telegram import send_with_keyboard
    send_with_keyboard(msg, compound_check_keyboard())


def missed_day_check() -> None:
    from apex.infra.db import Repositories
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    protocol = _load_protocol_safe()
    tz = ZoneInfo(protocol.profile.timezone) if protocol else timezone.utc
    today = datetime.now(tz).strftime("%Y-%m-%d")
    repos = Repositories()
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
    today = protocol_today(protocol).isoformat()
    lines = ["📊 <b>Week in review</b>\n"]
    for metric in protocol.tracking.metrics:
        logs = repos.logs.get_range(metric=metric.name, days=7, today=today)
        if not logs:
            lines.append(f"• {metric.name}: no data this week")
            continue
        values = [l["value"] for l in logs if isinstance(l["value"], (int, float))]
        if not values:
            lines.append(f"• {metric.name}: {len(logs)}/7 days logged")
            continue
        avg = sum(values) / len(values)
        target_str = f" / {metric.daily_target}{metric.unit_str}" if metric.daily_target else ""
        lines.append(
            f"• {metric.name}: avg {avg:.1f}{metric.unit_str}{target_str} ({len(logs)}/7 days logged)"
        )
    send("\n".join(lines))


_REGISTRY = {
    "morning_checkin": morning_checkin,
    "morning_injection_reminder": morning_injection_reminder,
    "injection_reminder": injection_reminder,
    "water_reminder": water_reminder,
    "bedtime_prompt": bedtime_prompt,
    "missed_day_check": missed_day_check,
    "weekly_summary": weekly_summary,
}

# Subset of _REGISTRY safe to fire from a protocol reminder (excludes weekly_summary
# and missed_day_check — those run only from their dedicated EventBridge rules).
_REMINDER_SAFE_JOBS = {
    k: _REGISTRY[k]
    for k in (
        "morning_checkin",
        "morning_injection_reminder",
        "injection_reminder",
        "water_reminder",
        "bedtime_prompt",
    )
}


def run(job: str) -> None:
    fn = _REGISTRY.get(job)
    if fn:
        logger.info(f"Running job: {job}")
        fn()
    else:
        logger.warning(f"Unknown job: {job}")
