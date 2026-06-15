"""Unit tests for the eval-harness state graders (evals/harness.py).

The graders are pure functions over a TurnResult snapshot — no Bedrock, no
moto. These tests are what make "the graders are unit-verified" true: a grader
bug would silently corrupt every scored eval run, so the graders themselves
get the cheapest layer that can express the check (EVALS.md §8).
"""
from typing import Any

from evals.harness import TurnResult, grade


def _result(**overrides) -> TurnResult:
    defaults: dict[str, Any] = dict(
        reply="ok",
        today_rows=[],
        protocol_before={},
        protocol_after={},
    )
    defaults.update(overrides)
    return TurnResult(**defaults)


def _rows(*pairs):
    return [{"metric": m, "value": v} for m, v in pairs]


# --------------------------------------------------------------------------- #
# grade() dispatch                                                            #
# --------------------------------------------------------------------------- #
def test_grade_fails_on_agent_error():
    passed, reason = grade({"grader": "logs"}, _result(error="Throttling: slow down"))
    assert not passed
    assert "Throttling" in reason


def test_grade_unknown_grader_fails():
    passed, reason = grade({"grader": "vibes"}, _result())
    assert not passed
    assert "unknown grader" in reason


def test_grade_defaults_to_logs_grader():
    case = {"expect_logs": [{"metric": "sleep", "value": 7.5}]}
    passed, _ = grade(case, _result(today_rows=_rows(("sleep", 7.5))))
    assert passed


# --------------------------------------------------------------------------- #
# logs grader                                                                 #
# --------------------------------------------------------------------------- #
def test_logs_grader_missing_metric_fails():
    case = {"expect_logs": [{"metric": "sleep", "value": 7.5}]}
    passed, reason = grade(case, _result(today_rows=_rows(("water", 60))))
    assert not passed
    assert "missing log for 'sleep'" in reason


def test_logs_grader_value_outside_tolerance_fails():
    case = {"expect_logs": [{"metric": "sleep", "value": 7.5}]}
    passed, reason = grade(case, _result(today_rows=_rows(("sleep", 7.0))))
    assert not passed
    assert "sleep=7.0" in reason


def test_logs_grader_per_case_and_per_expectation_tolerance():
    rows = _rows(("water", 31.0))
    case = {"expect_logs": [{"metric": "water", "value": 34}], "tolerance": 3.4}
    assert grade(case, _result(today_rows=rows))[0]
    case_per_exp = {"expect_logs": [{"metric": "water", "value": 34, "tolerance": 1}]}
    assert not grade(case_per_exp, _result(today_rows=rows))[0]


def test_logs_grader_forbid_other_logs():
    case = {
        "expect_logs": [{"metric": "sleep", "value": 8}],
        "forbid_other_logs": True,
    }
    rows = _rows(("sleep", 8), ("protein", 0))
    passed, reason = grade(case, _result(today_rows=rows))
    assert not passed
    assert "protein" in reason
    # without the flag, the extra row is tolerated
    del case["forbid_other_logs"]
    assert grade(case, _result(today_rows=rows))[0]


# --------------------------------------------------------------------------- #
# no_writes grader                                                            #
# --------------------------------------------------------------------------- #
def test_no_writes_grader():
    case = {"grader": "no_writes"}
    assert grade(case, _result())[0]
    passed, reason = grade(case, _result(today_rows=_rows(("protein", 0))))
    assert not passed
    assert "protein" in reason


# --------------------------------------------------------------------------- #
# protocol_diff grader                                                        #
# --------------------------------------------------------------------------- #
_BEFORE = {
    "profile": {"name": "Alex"},
    "tracking": {"metrics": [{"name": "protein", "daily_target": 180}]},
}


def _after(target=180, name="Alex"):
    return {
        "profile": {"name": name},
        "tracking": {"metrics": [{"name": "protein", "daily_target": target}]},
    }


def test_protocol_diff_expected_change_passes():
    case = {
        "grader": "protocol_diff",
        "expect_changes": {"tracking.metrics.protein.daily_target": 200},
    }
    result = _result(protocol_before=_BEFORE, protocol_after=_after(target=200))
    assert grade(case, result)[0]


def test_protocol_diff_field_did_not_change_fails():
    case = {
        "grader": "protocol_diff",
        "expect_changes": {"tracking.metrics.protein.daily_target": 200},
    }
    passed, reason = grade(case, _result(protocol_before=_BEFORE, protocol_after=_after()))
    assert not passed
    assert "did not" in reason


def test_protocol_diff_unexpected_change_fails():
    case = {
        "grader": "protocol_diff",
        "expect_changes": {"tracking.metrics.protein.daily_target": 200},
    }
    result = _result(
        protocol_before=_BEFORE, protocol_after=_after(target=200, name="Mallory")
    )
    passed, reason = grade(case, result)
    assert not passed
    assert "profile.name" in reason


def test_protocol_diff_any_sentinel_accepts_any_new_value():
    case = {
        "grader": "protocol_diff",
        "expect_changes": {"tracking.metrics.protein.daily_target": "ANY"},
    }
    result = _result(protocol_before=_BEFORE, protocol_after=_after(target=999))
    assert grade(case, result)[0]


def test_protocol_diff_no_changes_at_all():
    case = {"grader": "protocol_diff", "expect_changes": {}}
    assert grade(case, _result(protocol_before=_BEFORE, protocol_after=_after()))[0]
