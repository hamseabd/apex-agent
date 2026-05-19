from __future__ import annotations

from strands import Agent

from apex.domain.models import Protocol
from apex.infra.db import Repositories
from apex.infra.storage import ProtocolStore
from apex.infra.telemetry import logger
from apex.tools.factory import build_tools

_SYSTEM_PROMPT = """You are Apex — a personal health and performance accountability coach.

You have tools to log and read the user's tracked metrics. Use them.

ALWAYS LOG FIRST: If the user's message contains any loggable data, call the appropriate
log tool immediately before responding. Examples:
- "slept 7 hours" → log_sleep(value=7)
- "hit 180g protein" → log_protein(value=180)
- "ran 3 miles, drank 60oz water" → log_run(value=3) AND log_water(value=60)

After logging, confirm with the value and progress toward any target.

When answering questions:
- Pull real data first using read tools. Never guess.
- Show trends, not just today's snapshot.
- Be direct. Use numbers. No filler.

Personality: coach, not cheerleader. Clear, concise, honest."""


def build_agent(protocol: Protocol, repos: Repositories, store: ProtocolStore) -> Agent:
    """
    Build a Strands Agent with tools generated from the user's protocol.
    Called at Lambda cold start. Tool list is dynamic — derived entirely from protocol.
    """
    tools = build_tools(protocol, repos)
    logger.info("Agent built", extra={"tool_count": len(tools), "tools": [t.__name__ for t in tools]})
    return Agent(system_prompt=_SYSTEM_PROMPT, tools=tools)
