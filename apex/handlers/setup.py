from __future__ import annotations
import html as _html
import json
from datetime import date
from functools import lru_cache

import boto3

from apex.infra.telegram import send
from apex.infra.telemetry import logger

_ALLOWED_PROTOCOL_KEYS = frozenset({
    "goal", "metrics", "supplements", "schedule", "compounds", "profile", "version",
})
_MAX_CONTEXT_BYTES = 50_000

@lru_cache(maxsize=1)
def _bedrock_client():
    from apex.settings import get_settings
    return boto3.client("bedrock-runtime", region_name=get_settings().aws_region)


def _call_llm(system_prompt: str, user_message: str) -> str:
    """Single-shot Bedrock call — no agent overhead, no history accumulation."""
    from apex.settings import get_settings
    response = _bedrock_client().converse(
        modelId=get_settings().bedrock_model_id,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_message}]}],
        inferenceConfig={"maxTokens": 2048},
    )
    return response["output"]["message"]["content"][0]["text"]

_SETUP_TTL = 1800  # 30 minutes for setup flow

_STAGE_PROMPTS = {
    "goal": (
        "Ask what their main health goal is. "
        'Extract: {"goal": "<string>"}.'
    ),
    "metrics": (
        "Ask what they want to track daily (e.g. sleep, protein, water, weight, energy, meditation — whatever fits their lifestyle). "
        'Extract: {"metrics": ["<name1>", "<name2>", ...]}.'
    ),
    "supplements": (
        "Ask about any supplements they take. Collect morning and evening separately with name and dose. "
        "If none, use empty lists. "
        'Extract: {"supplements": {"morning": [{"name": str, "dose": str}], "evening": [...]}}.'
    ),
    "schedule": (
        "Ask what time they wake up. Suggest 10am and 3pm water reminders. "
        "All times as HH:MM 24-hour. "
        'Extract: {"schedule": {"morning_checkin": "HH:MM", "reminders": []}}.'
    ),
    "compounds": (
        "Ask if they track any compounds (peptides, SARMs, hormones, etc). "
        "If yes, collect name, on/off cycle weeks, and dosing. "
        "If no, extract null. "
        'Extract: {"compounds": [...]} or {"compounds": null}.'
    ),
}

_STAGE_ORDER = ["goal", "metrics", "supplements", "schedule", "compounds", "confirm"]


def handle_setup_start(repos) -> None:
    repos.users.set_state("setup_in_progress", {"step": "goal", "protocol": {}}, ttl_seconds=_SETUP_TTL)
    send(
        "👋 <b>Welcome to Apex!</b>\n\n"
        "I'll help you set up your personal health protocol — takes about 10 minutes.\n\n"
        "What's your main health goal? "
        "(e.g. lose fat, build muscle, improve sleep, peak performance)"
    )


def handle_setup_message(text: str, step: str, context: dict, repos) -> None:
    if step == "confirm":
        if text.strip().lower() == "confirm":
            _finalize(context["protocol"], repos)
        else:
            _apply_edit(text, context, repos)
        return

    instruction = _STAGE_PROMPTS.get(step, "")
    raw = _ask_claude(text, step, context.get("protocol", {}), instruction)

    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Setup Claude response not JSON", extra={"raw": raw[:200]})
        send(raw)
        return

    reply = envelope.get("reply", "")
    extracted = envelope.get("extracted") or {}
    if isinstance(extracted, dict):
        extracted = {k: v for k, v in extracted.items() if k in _ALLOWED_PROTOCOL_KEYS}
    else:
        extracted = {}
    advance = envelope.get("advance", False)

    if reply:
        send(reply)

    if advance and extracted:
        updated = {**context.get("protocol", {}), **extracted}
        if len(json.dumps(updated).encode()) > _MAX_CONTEXT_BYTES:
            logger.warning("Extracted data too large, not advancing", extra={"size": len(json.dumps(updated))})
            repos.users.set_state("setup_in_progress", context, ttl_seconds=_SETUP_TTL)
            send("Something went wrong processing that — could you try rephrasing?")
            return
        next_step = _next_stage(step)
        repos.users.set_state(
            "setup_in_progress",
            {"step": next_step, "protocol": updated},
            ttl_seconds=_SETUP_TTL,
        )
        if next_step == "confirm":
            _send_summary(updated)
    else:
        repos.users.set_state("setup_in_progress", context, ttl_seconds=_SETUP_TTL)


def _next_stage(current: str) -> str:
    try:
        idx = _STAGE_ORDER.index(current)
        return _STAGE_ORDER[idx + 1] if idx + 1 < len(_STAGE_ORDER) else "confirm"
    except ValueError:
        return "goal"


def _send_summary(protocol: dict) -> None:
    goal = _html.escape(str(protocol.get("goal", "—")))
    metrics = protocol.get("metrics", [])
    metrics_str = _html.escape(", ".join(str(m) for m in metrics)) if metrics else "none"
    sc = protocol.get("schedule", {})
    checkin = sc.get("morning_checkin", "07:00")
    compounds = protocol.get("compounds") or []
    compound_str = (
        f"\nCompounds: {_html.escape(', '.join(c['name'] if isinstance(c, dict) else str(c) for c in compounds))}"
        if compounds else ""
    )
    send(
        f"<b>Here's your protocol:</b>\n\n"
        f"Goal: {goal}\n"
        f"Tracking: {metrics_str}\n"
        f"Morning checkin: {checkin}"
        f"{compound_str}\n\n"
        "Say <b>confirm</b> to lock it in, or tell me what to change."
    )


def _apply_edit(text: str, context: dict, repos) -> None:
    """User wants to change something in the summary — use Claude."""
    raw = _call_llm(
        system_prompt=(
            "The user wants to change their health protocol before confirming. "
            "Apply the change and return ONLY JSON (no markdown): "
            '{"updated_protocol": {...}, "reply": "<confirmation message>"}'
        ),
        user_message=(
            f"Current protocol: {json.dumps(context.get('protocol', {}))}\n"
            f"User change: {text}"
        ),
    )
    try:
        envelope = json.loads(raw)
        updated = envelope.get("updated_protocol", context.get("protocol", {}))
        if not isinstance(updated, dict):
            send("I couldn't apply that change — please try rephrasing.")
            return
        updated = {k: v for k, v in updated.items() if k in _ALLOWED_PROTOCOL_KEYS}
        reply = envelope.get("reply", "Updated.")
        repos.users.set_state(
            "setup_in_progress",
            {"step": "confirm", "protocol": updated},
            ttl_seconds=_SETUP_TTL,
        )
        send(reply)
        _send_summary(updated)
    except json.JSONDecodeError:
        send("I couldn't parse that change — could you rephrase it?")


def _finalize(protocol: dict, repos) -> None:
    """Save protocol to S3, generate research docs, clear state."""
    from apex.infra.storage import ProtocolStore
    from apex.domain.models import Protocol as ProtocolModel

    send("✅ Protocol locked. Setting up your knowledge base...")
    repos.users.clear_state()

    # Remove null compounds section if empty
    if "compounds" in protocol and not protocol["compounds"]:
        protocol.pop("compounds")

    # Build a proper Protocol model to validate and save
    try:
        # Normalize metrics from list of strings to list of dicts
        metrics_raw = protocol.get("metrics", [])
        if metrics_raw and isinstance(metrics_raw[0], str):
            protocol["metrics"] = [{"name": m} for m in metrics_raw]

        # Build the full protocol structure
        full_protocol = {
            "version": "2",
            "profile": {
                "name": protocol.get("profile", {}).get("name", "User") if isinstance(protocol.get("profile"), dict) else "User",
                "goal": protocol.get("goal", ""),
                "timezone": "America/New_York",
                "start_date": date.today().isoformat(),
            },
            "tracking": {
                "metrics": [
                    {"name": m} if isinstance(m, str) else m
                    for m in protocol.get("metrics", [])
                ]
            },
            "supplements": protocol.get("supplements"),
            "compounds": protocol.get("compounds"),
            "schedule": protocol.get("schedule", {"morning_checkin": "07:00", "reminders": []}),
        }

        model = ProtocolModel(**full_protocol)
        store = ProtocolStore()
        store.save(model)

        send(
            "Done! Your reminders are live — the hourly scheduler picks them up "
            "straight from your protocol.\n\n"
            "Just talk to me naturally — I'll log anything you mention."
        )
    except Exception as e:
        logger.error(f"Setup finalization failed: {e}")
        send(
            "⚠️ There was an issue saving your protocol. "
            "Send /setup to try again."
        )


def _ask_claude(user_text: str, step: str, protocol_so_far: dict, instruction: str) -> str:
    """Call Claude for the current setup stage. Returns raw JSON string."""
    return _call_llm(
        system_prompt=(
            f"You are guiding a health bot setup. Current stage: '{step}'. {instruction}\n\n"
            "Respond ONLY with a JSON object (no markdown fences) in this shape:\n"
            '{"reply": "<your message to the user>", '
            '"extracted": <dict of extracted data or null>, '
            '"advance": <true if you extracted all required data for this stage, false otherwise>}\n\n'
            "If the user asks a research question instead of answering, "
            "answer it in reply and set advance=false."
        ),
        user_message=(
            f"Protocol so far: {json.dumps(protocol_so_far)}\n"
            f"User: {user_text}"
        ),
    )
