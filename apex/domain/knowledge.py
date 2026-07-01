from __future__ import annotations

REFUSAL = "I don't have a grounded source for that."
DISCLAIMER = "⚠️ Informational, from your documents — not medical advice."


def assemble_sources(docs: list[dict]) -> str:
    """Wrap each doc in a labeled <source> tag so the model can cite by filename."""
    return "\n".join(
        f'<source name="{d["source"]}">\n{d["text"]}\n</source>'
        for d in docs
    )


def grounding_system_prompt(sources_block: str) -> str:
    return (
        "You answer health/research questions using ONLY the provided sources below. "
        "Do not use outside knowledge.\n"
        f'If the sources do not contain the answer, respond with exactly: "{REFUSAL}"\n'
        "When you do answer, cite the source filename in brackets after each claim, "
        "e.g. [creatine.md]. Frame the answer as informational, not medical advice.\n\n"
        "SOURCES:\n"
        f"{sources_block}"
    )
