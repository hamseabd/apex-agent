
import apex.tools.knowledge as kn
from apex.domain.knowledge import DISCLAIMER, REFUSAL


class FakeStore:
    def __init__(self, docs, tokens=10):
        self._docs = docs
        self._tokens = tokens

    def load_corpus(self):
        return self._docs

    def total_tokens(self):
        return self._tokens


def test_empty_corpus_refuses_without_bedrock(monkeypatch):
    called = {"n": 0}

    def _boom(*a, **k):
        called["n"] += 1
        raise AssertionError("Bedrock should not be called on empty corpus")

    monkeypatch.setattr(kn, "_call_bedrock", _boom)
    result = kn._ask(FakeStore(docs=[]), "anything")
    assert result == REFUSAL
    assert called["n"] == 0


def test_grounded_answer_appends_disclaimer(monkeypatch):
    monkeypatch.setattr(
        kn, "_call_bedrock", lambda system, question: "Creatine is 5g/day [creatine.md]."
    )
    store = FakeStore(docs=[{"source": "creatine.md", "text": "5g/day"}])
    result = kn._ask(store, "creatine dose?")
    assert "[creatine.md]" in result
    assert DISCLAIMER in result


def test_model_refusal_has_no_disclaimer(monkeypatch):
    monkeypatch.setattr(kn, "_call_bedrock", lambda system, question: REFUSAL)
    store = FakeStore(docs=[{"source": "x.md", "text": "unrelated"}])
    result = kn._ask(store, "something the corpus lacks")
    assert result == REFUSAL
    assert DISCLAIMER not in result


def test_oversize_corpus_warns_but_serves(monkeypatch):
    warnings = []
    monkeypatch.setattr(kn.logger, "warning", lambda msg, **k: warnings.append(msg))
    monkeypatch.setattr(kn, "_call_bedrock", lambda system, question: "ans [x.md]")
    store = FakeStore(docs=[{"source": "x.md", "text": "data"}], tokens=200_000)
    result = kn._ask(store, "q")
    assert "ans [x.md]" in result
    assert warnings  # a warning was logged
