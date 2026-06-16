# Eval run history

One row per scored run (appended by `python -m evals.report`). Committed so the
suite is visible on GitHub without anyone triggering CI. The first scored run
(2026-06-16) used real Bedrock (`APEX_EVAL_LIVE=1`) with DynamoDB/S3 mocked via
moto passthrough.

The initial full run scored E6 3/9 — but those were grader false-negatives, not
agent failures: the agent set numeric targets correctly (e.g. protein → 200),
which round-trip as Decimal `200.0`, and the protocol-diff grader compared string
forms (`"200.0" != "200"`). Fixed with a numeric-aware compare; E6 re-ran 9/9.
True result is 66/66. **TODO: one clean end-to-end run post-fix to confirm 66/66
in a single pass** (E1/E3/E4/E9 use different graders and were unaffected).

| Date | Git SHA | Model | Per-category passes | Note |
|------|---------|-------|---------------------|------|
| 2026-06-16 | 2070b76 | us.anthropic.claude-sonnet-4-6 | E1:24/24 E3:9/9 E4:18/18 E6:9/9 E9:6/6 | E6 via post-fix re-run; grader bug corrected same day |
