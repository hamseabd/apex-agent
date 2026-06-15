# evals/ — L2 capability evals

State-grading behavioral evals for the Apex agent. Strategy: [../EVALS.md](../EVALS.md).
Build plan: [../EVALS_IMPLEMENTATION_PLAN.md](../EVALS_IMPLEMENTATION_PLAN.md).

These run the **real** agent (real Bedrock) against **mocked** AWS (moto), then
grade what actually persisted to the mock DynamoDB/S3. No LLM judge in v1 — every
grader is deterministic code.

```
evals/
├── conftest.py          # --eval-trials / --record options; live-Bedrock gate
├── harness.py           # run_turn() + state graders (logs / no_writes / protocol_diff)
├── test_capability.py   # parametrized over cases/*.yaml
├── report.py            # latest.jsonl -> markdown + HISTORY.md
├── fixtures/eval_protocol.yaml   # FROZEN protocol (bump dataset version to change)
├── cases/               # E1, E3, E4, E6, E9 golden datasets (22 cases)
├── MANIFEST.yaml        # dataset version + case counts
└── results/             # latest.jsonl (gitignored) + HISTORY.md (committed)
```

## Run

Collection is always free and safe (no Bedrock at import time):

```bash
PYTHONPATH=. pytest evals/ --collect-only          # lists all 22 cases
PYTHONPATH=. pytest evals/ -m capability            # skips unless live mode on
```

A real scored run needs Bedrock creds and live mode:

```bash
APEX_EVAL_LIVE=1 BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0 \
  PYTHONPATH=. pytest evals/ -m capability --eval-trials=3
PYTHONPATH=. python -m evals.report                 # render + append HISTORY.md
```

Cost: ~22 cases × trials × (~2k in + ~300 out) on Sonnet ≈ ~$0.40 per 1-trial run.
