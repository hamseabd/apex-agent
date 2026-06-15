"""L2 capability evals — parametrized from evals/cases/*.yaml.

Each case is run `--eval-trials` times against the real agent. Reliability-
critical categories (E1) are read as pass^k by the report; the test itself
records every (case, trial) outcome to results/latest.jsonl regardless.

Collection is always safe (no Bedrock at import). Execution is gated on the
`live_bedrock` fixture, so `pytest evals/` collects + skips with no creds and
runs for real with APEX_EVAL_LIVE=1.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from evals.harness import grade, run_turn

CASES_DIR = Path(__file__).parent / "cases"
RESULTS_DIR = Path(__file__).parent / "results"


def _load_cases() -> list[dict]:
    cases: list[dict] = []
    for path in sorted(CASES_DIR.glob("*.yaml")):
        for case in yaml.safe_load(path.read_text()) or []:
            case["_file"] = path.name
            cases.append(case)
    return cases


ALL_CASES = _load_cases()


def _record(row: dict) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    with (RESULTS_DIR / "latest.jsonl").open("a") as fh:
        fh.write(json.dumps(row) + "\n")


@pytest.mark.capability
@pytest.mark.parametrize("case", ALL_CASES, ids=[c["id"] for c in ALL_CASES])
def test_case(case, live_bedrock, eval_trials, request):
    """Run one golden case `eval_trials` times; every trial must pass."""
    failures = []
    for trial in range(eval_trials):
        result = run_turn(case["utterance"])
        passed, reason = grade(case, result)
        _record({
            "id": case["id"],
            "category": case.get("category"),
            "trial": trial,
            "passed": passed,
            "reason": reason,
            "model_id": os.environ.get("BEDROCK_MODEL_ID"),
            "dataset_version": 1,
            "git_sha": os.environ.get("GIT_SHA", ""),
            "reply": result.reply,
            "tool_calls": result.tool_calls,
            "latency_s": result.latency_s,
        })
        if not passed:
            failures.append(f"trial {trial}: {reason}")

    assert not failures, f"{case['id']} failed {len(failures)}/{eval_trials}: " + "; ".join(failures)
