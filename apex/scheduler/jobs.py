from __future__ import annotations
from apex.infra.telemetry import logger
from apex.infra.telegram import send


def run(job: str) -> None:
    """Dispatch a scheduled job by name."""
    registry = {
        "morning_checkin": morning_checkin,
    }
    fn = registry.get(job)
    if fn:
        logger.info(f"Running job: {job}")
        fn()
    else:
        logger.warning(f"Unknown job: {job}")


def morning_checkin() -> None:
    send(
        "☀️ <b>Good morning!</b>\n\n"
        "How did you sleep? Just tell me naturally — "
        "I'll log it and anything else you mention."
    )
