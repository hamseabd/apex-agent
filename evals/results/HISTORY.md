# Eval run history

One row per scored run (appended by `python -m evals.report`). Committed so the
suite is visible on GitHub without anyone triggering CI. All runs use real Bedrock
(`APEX_EVAL_LIVE=1`) with DynamoDB/S3 mocked via moto passthrough.

The first run (2070b76) scored E6 3/9 — but those were grader false-negatives, not
agent failures. The agent set numeric targets correctly (e.g. protein → 200), which
round-trip as Decimal `200.0`, and the protocol-diff grader compared string forms
(`"200.0" != "200"`). Fixed with a numeric-aware compare. The clean 3-trial run
after the fix (bb99cef) scored **66/66**.

| Date | Git SHA | Model | Per-category passes | Note |
|------|---------|-------|---------------------|------|
| 2026-06-16 | 2070b76 | us.anthropic.claude-sonnet-4-6 | E1:24/24 E3:9/9 E4:18/18 E6:3/9 E9:6/6 | first run — E6 fails were a grader bug (str vs Decimal), not the agent |
| 2026-06-16 | bb99cef | us.anthropic.claude-sonnet-4-6 | E1:24/24 E3:9/9 E4:18/18 E6:9/9 E9:6/6 | clean 3-trial run after grader fix — 66/66, E1 pass^k 8/8, E4 false-log 0% |
