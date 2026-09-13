from apex.domain.knowledge import (
    DISCLAIMER,
    REFUSAL,
    assemble_sources,
    grounding_system_prompt,
)


def test_assemble_sources_wraps_each_doc():
    docs = [
        {"source": "creatine.md", "text": "5g/day."},
        {"source": "zinc.md", "text": "Zinc doc."},
    ]
    block = assemble_sources(docs)
    assert '<source name="creatine.md">' in block
    assert "5g/day." in block
    assert '<source name="zinc.md">' in block
    assert block.count("<source") == 2


def test_assemble_sources_empty():
    assert assemble_sources([]) == ""


def test_grounding_prompt_contains_rules_and_sources():
    prompt = grounding_system_prompt('<source name="a.md">hi</source>')
    assert "ONLY" in prompt
    assert REFUSAL in prompt
    assert '<source name="a.md">hi</source>' in prompt


def test_constants_exact_strings():
    assert REFUSAL == "I don't have a grounded source for that."
    assert DISCLAIMER == "⚠️ Informational, from your documents — not medical advice."
