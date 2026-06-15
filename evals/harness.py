"""State-grading eval harness for Apex.

The whole premise (EVALS.md §2): every consequential agent action lands in a
database we can inspect in-process. So we run the *real* agent against *mocked*
AWS (moto), then query the mock table/bucket and grade what actually persisted.

`run_turn()` builds the real Strands agent (real Bedrock model) against a frozen
protocol on mock S3 and a mock DynamoDB table, sends one utterance, and returns a
`TurnResult` snapshot of everything that changed. `grade()` scores a case against
that snapshot using a deterministic state grader — no LLM judge in v1.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import boto3
import moto

from apex.domain.dates import local_today

FIXTURES = Path(__file__).parent / "fixtures"
EVAL_PROTOCOL = FIXTURES / "eval_protocol.yaml"

_BUCKET = "apex-eval-bucket"
_TABLE = "apex-eval"
_USER_ID = "999"


# --------------------------------------------------------------------------- #
# Mock AWS                                                                     #
# --------------------------------------------------------------------------- #
def _create_table(resource):
    """Create the single-table schema (mirrors tests/conftest.py)."""
    return resource.create_table(
        TableName=_TABLE,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )


# --------------------------------------------------------------------------- #
# Result snapshot                                                             #
# --------------------------------------------------------------------------- #
@dataclass
class TurnResult:
    reply: str
    today_rows: list[dict]                 # log rows written for today
    protocol_before: dict                  # protocol.model_dump() before the turn
    protocol_after: dict                   # protocol.model_dump() after the turn
    tool_calls: list[str] = field(default_factory=list)
    latency_s: float = 0.0
    error: str | None = None


# --------------------------------------------------------------------------- #
# Harness                                                                     #
# --------------------------------------------------------------------------- #
def run_turn(
    utterance: str,
    *,
    protocol_yaml: str | None = None,
    seed_logs: list[dict] | None = None,
    user_id: str = _USER_ID,
) -> TurnResult:
    """Run one real agent turn against mock AWS and snapshot the resulting state.

    Bedrock is REAL — this call costs tokens. DynamoDB/S3 are moto mocks.
    """
    from apex.infra.db import Repositories
    from apex.infra.storage import ProtocolStore
    from apex.agent import build_agent

    yaml_text = protocol_yaml or EVAL_PROTOCOL.read_text()

    with moto.mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(resource)
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=_BUCKET)
        s3.put_object(Bucket=_BUCKET, Key="apex.yaml", Body=yaml_text.encode("utf-8"))

        repos = Repositories(table=table, user_id=user_id)
        store = ProtocolStore(bucket=_BUCKET)
        protocol = store.load()
        protocol_before = protocol.model_dump(exclude_none=True)

        if seed_logs:
            for row in seed_logs:
                repos.logs.write(
                    metric=row["metric"],
                    value=row["value"],
                    log_date=row.get("date", local_today(protocol.profile.timezone).isoformat()),
                    notes=row.get("notes", ""),
                )

        agent = build_agent(protocol, repos, store)

        start = time.time()
        error = None
        reply = ""
        try:
            reply = str(agent(utterance))
        except Exception as exc:  # surface Bedrock/agent errors as a failed turn
            error = f"{type(exc).__name__}: {exc}"
        latency = time.time() - start

        today = local_today(protocol.profile.timezone).isoformat()
        today_rows = repos.logs.get_day(today)
        protocol_after = store.load().model_dump(exclude_none=True)

        return TurnResult(
            reply=reply,
            today_rows=today_rows,
            protocol_before=protocol_before,
            protocol_after=protocol_after,
            tool_calls=_extract_tool_calls(agent),
            latency_s=round(latency, 2),
            error=error,
        )


def _extract_tool_calls(agent) -> list[str]:
    """Best-effort pull of tool names from the Strands message trace."""
    names: list[str] = []
    for msg in getattr(agent, "messages", []) or []:
        content = msg.get("content") if isinstance(msg, dict) else None
        for block in content or []:
            if isinstance(block, dict) and "toolUse" in block:
                name = block["toolUse"].get("name")
                if name:
                    names.append(name)
    return names


# --------------------------------------------------------------------------- #
# State graders                                                              #
# --------------------------------------------------------------------------- #
def _rows_as_map(rows: list[dict]) -> dict[str, float]:
    return {r["metric"]: r["value"] for r in rows}


def grade(case: dict, result: TurnResult) -> tuple[bool, str]:
    """Dispatch a case to its grader. Returns (passed, human-readable reason)."""
    if result.error:
        return False, f"agent error: {result.error}"

    grader = case.get("grader", "logs")
    if grader == "logs":
        return _grade_logs(case, result)
    if grader == "no_writes":
        return _grade_no_writes(case, result)
    if grader == "protocol_diff":
        return _grade_protocol_diff(case, result)
    return False, f"unknown grader: {grader}"


def _grade_logs(case: dict, result: TurnResult) -> tuple[bool, str]:
    expected = case.get("expect_logs", [])
    tol = float(case.get("tolerance", 0))
    actual = _rows_as_map(result.today_rows)

    for exp in expected:
        metric, want = exp["metric"], exp["value"]
        if metric not in actual:
            return False, f"missing log for '{metric}' (got {sorted(actual)})"
        got = actual[metric]
        per_tol = float(exp.get("tolerance", tol))
        if abs(got - want) > per_tol:
            return False, f"{metric}={got}, expected {want} (±{per_tol})"

    if case.get("forbid_other_logs"):
        extra = set(actual) - {e["metric"] for e in expected}
        if extra:
            return False, f"unexpected extra logs: {sorted(extra)}"

    return True, "ok"


def _grade_no_writes(case: dict, result: TurnResult) -> tuple[bool, str]:
    if result.today_rows:
        metrics = sorted(_rows_as_map(result.today_rows))
        return False, f"expected no writes, but logged: {metrics}"
    return True, "ok (no writes)"


def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten a protocol dict to leaf paths. Lists of named dicts (metrics,
    compounds, supplements) are keyed by name so paths are stable and readable.
    """
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, list):
        if obj and all(isinstance(i, dict) and "name" in i for i in obj):
            for item in obj:
                out.update(_flatten(item, f"{prefix}.{item['name']}"))
        else:
            out[prefix] = repr(obj)
    else:
        out[prefix] = obj
    return out


def _grade_protocol_diff(case: dict, result: TurnResult) -> tuple[bool, str]:
    before = _flatten(result.protocol_before)
    after = _flatten(result.protocol_after)
    changed = {
        k: (before.get(k), after.get(k))
        for k in set(before) | set(after)
        if before.get(k) != after.get(k)
    }
    expected = case.get("expect_changes", {})  # {path: value}

    for path, want in expected.items():
        if path not in changed:
            return False, f"expected '{path}' to change, but it did not ({sorted(changed)})"
        got = after.get(path)
        if want != "ANY" and str(got) != str(want):
            return False, f"'{path}'={got!r}, expected {want!r}"

    if case.get("forbid_other_changes", True):
        unexpected = set(changed) - set(expected)
        if unexpected:
            return False, f"unexpected protocol changes: {sorted(unexpected)}"

    return True, "ok"
