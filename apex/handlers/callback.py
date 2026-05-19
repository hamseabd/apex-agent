from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def handle_callback(callback_query: dict) -> None:
    """Inline keyboard callback handler. Sprint 4 — inline buttons implemented here."""
    logger.info("Callback received", extra={"data": callback_query.get("data", "")})
