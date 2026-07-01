from __future__ import annotations

from functools import lru_cache

import boto3
from strands import tool

from apex.domain.knowledge import (
    DISCLAIMER,
    REFUSAL,
    assemble_sources,
    grounding_system_prompt,
)
from apex.infra.telemetry import logger

_TOKEN_WARN_THRESHOLD = 150_000


@lru_cache(maxsize=1)
def _bedrock_client():
    from apex.settings import get_settings
    return boto3.client("bedrock-runtime", region_name=get_settings().aws_region)


def _call_bedrock(system: str, question: str) -> str:
    """Single grounded converse call with a cached system block."""
    from apex.settings import get_settings
    response = _bedrock_client().converse(
        modelId=get_settings().bedrock_model_id,
        system=[{"text": system}, {"cachePoint": {"type": "default"}}],
        messages=[{"role": "user", "content": [{"text": question}]}],
        inferenceConfig={"maxTokens": 1024},
    )
    return response["output"]["message"]["content"][0]["text"]


def _ask(store, question: str) -> str:
    """Core logic — separated from the @tool wrapper for direct unit testing."""
    docs = store.load_corpus()
    if not docs:
        return REFUSAL

    if store.total_tokens() > _TOKEN_WARN_THRESHOLD:
        logger.warning(
            "Knowledge corpus exceeds prompt-caching sweet spot; consider vector RAG",
            extra={"tokens": store.total_tokens()},
        )

    system = grounding_system_prompt(assemble_sources(docs))
    answer = _call_bedrock(system, question).strip()

    if answer == REFUSAL:
        return REFUSAL
    return f"{answer}\n\n{DISCLAIMER}"


def build_knowledge_tools(store) -> list:
    """Build the ask_knowledge_base tool bound to a KnowledgeStore."""

    def ask_knowledge_base(question: str) -> str:
        """Answer a health/research question grounded ONLY in the user's knowledge-base
        documents, with citations. Use for supplement/compound/protocol-rationale questions.
        Do NOT use for the user's own logged metrics — those have their own tools."""
        return _ask(store, question)

    return [tool(ask_knowledge_base)]
