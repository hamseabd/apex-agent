"""Eval-suite pytest config.

These evals call REAL Bedrock, so they never run as part of `pytest tests/`
(testpaths is pinned to tests/). They run only when explicitly targeted
(`pytest evals/`) AND live mode is enabled, so collection is always safe and
free; execution requires credentials.

Enable a live run with:
    APEX_EVAL_LIVE=1 BEDROCK_MODEL_ID=... AWS_PROFILE=...  pytest evals/ -m capability
"""
from __future__ import annotations

import os

import pytest

# Settings/boto need these present at import time even for collection.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "999")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("CONFIG_BUCKET", "apex-eval-bucket")
os.environ.setdefault("TABLE_NAME", "apex-eval")
# claude-sonnet-4 (20250514) is now provider-marked Legacy and access-denied on
# Bedrock; us.anthropic.claude-sonnet-4-6 is the current active Sonnet profile.
os.environ.setdefault("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")


def pytest_addoption(parser):
    parser.addoption(
        "--eval-trials", action="store", default="1", type=int,
        help="Number of trials per case (pass^k for reliability-critical cases).",
    )
    parser.addoption(
        "--record", action="store_true", default=False,
        help="Record a passing transcript as the reference artifact for a case.",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "capability: L2 evals — real Bedrock + moto AWS")
    config.addinivalue_line("markers", "quality: L3 evals — LLM-as-judge (roadmap)")


@pytest.fixture(scope="session")
def live_bedrock():
    """Skip the whole capability suite unless live mode is explicitly enabled."""
    if os.environ.get("APEX_EVAL_LIVE") != "1":
        pytest.skip(
            "live Bedrock disabled — set APEX_EVAL_LIVE=1 (plus AWS creds + "
            "BEDROCK_MODEL_ID) to run capability evals"
        )
    return True


@pytest.fixture(scope="session")
def eval_trials(request):
    return request.config.getoption("--eval-trials")
