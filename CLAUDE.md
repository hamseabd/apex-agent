# CLAUDE.md — Apex

## Project Overview

Apex is a self-hosted Telegram health accountability bot deployed on AWS Lambda. It is the successor to Maxy — built from scratch with production-grade architecture as a portfolio showcase for an AI engineer job search.

**The architectural headline:** Tools are generated at runtime from the user's `apex.yaml` protocol. Add "meditation" to your protocol → `log_meditation` tool appears in the agent. Zero code changes. Ever.

## Tech Stack

- Python 3.12, pyproject.toml (not requirements.txt)
- AWS Lambda (Docker/ECR), DynamoDB (single-table), S3, Bedrock, EventBridge, API Gateway
- Strands Agents SDK + Claude via AWS Bedrock
- Pydantic v2 (domain models + settings)
- AWS Powertools v3 (Logger, Tracer, Metrics on every Lambda handler)
- ruamel.yaml (comment-preserving YAML round-trips)
- moto (real AWS mocking in tests — not MagicMock)
- GitHub Actions CI

## Key Patterns

- **Protocol-first:** `apex.yaml` on S3 is the single source of truth. All bot behavior — tools, reminders, targets, compounds — derives from it.
- **Dynamic tools:** `apex/tools/factory.py:build_tools(protocol, repos)` generates `log_X` and `get_X_logs` tools from `protocol.tracking.metrics` at cold start. No metric names are hardcoded anywhere in business logic.
- **Domain isolation:** `apex/domain/` has zero AWS imports. Pure Python, Pydantic v2. Testable without boto3.
- **Repository pattern:** `apex/infra/db.py` exposes `LogRepository` and `UserRepository`. Handlers never touch DynamoDB directly.
- **Dependency injection:** `Repositories` container passed into agent, tools, and handlers. Makes testing clean.
- **Thin Lambda adapters:** `lambda_webhook.py` and `lambda_scheduler.py` are ~20 lines each. All logic lives in `apex/`.
- **Powertools everywhere:** Both Lambda handlers decorated with `@tracer.capture_lambda_handler`, `@logger.inject_lambda_context`, `@metrics.log_metrics`.

## Single-Table DynamoDB Schema

Table: `apex` | PK (String) + SK (String) | GSI1 (GSI1PK + GSI1SK)

| Entity | PK | SK | GSI1PK | GSI1SK |
|--------|----|----|--------|--------|
| User profile | `U#<id>` | `#PROFILE` | — | — |
| State machine | `U#<id>` | `#STATE` | — | — |
| Daily log | `U#<id>` | `LOG#<date>#<metric>` | `U#<id>#<metric>` | `<date>` |
| Streak | `U#<id>` | `STREAK#<metric>` | — | — |

GSI1 enables: `get_range(metric, days)` → time-range query per metric.

## Protocol Schema (`apex.yaml`)

```yaml
version: "2"
profile: { name, goal, timezone, start_date }
tracking:
  metrics:
    - { name, type, unit, daily_target }   # any metric — generates tools
supplements:
  morning: [{name, dose}]
  evening: [{name, dose}]
compounds:                                  # optional — remove to disable
  - { name, cycle: {on_weeks, off_weeks}, dosing: {am, pm}, intro: [], start_date }
schedule:
  morning_checkin: "HH:MM"
  reminders: [{time, job}]
```

## Commands

```bash
# Run tests (use project venv)
.venv/bin/pytest tests/ -v

# Install deps
pip install -e ".[dev]"

# Deploy code changes
./scripts/deploy.sh

# First-time setup
./scripts/store_secrets.sh   # store Telegram creds in SSM
./scripts/bootstrap.sh       # Terraform apply + Docker build + webhook registration
```

## Code Layout

```
apex/
├── domain/         # Pure Python — models.py (Protocol, Metric, Compound, etc.)
├── infra/          # AWS adapters — db.py, storage.py, telegram.py, telemetry.py
├── tools/          # factory.py (dynamic tool generator), core.py, compound.py
├── handlers/       # message.py, setup.py, callback.py
├── scheduler/      # jobs.py (scheduled job functions)
├── agent.py        # build_agent(protocol, repos, store) → Strands Agent
└── settings.py     # get_settings() via pydantic-settings

lambda_webhook.py   # Thin adapter — Powertools decorated, delegates to handlers
lambda_scheduler.py # Thin adapter — Powertools decorated, delegates to jobs
terraform/          # All AWS infra (DynamoDB, S3, Lambda, API Gateway, EventBridge, IAM)
scripts/            # bootstrap.sh, deploy.sh, store_secrets.sh
tests/
├── domain/         # Pure unit tests — no mocking needed
├── tools/          # Tool factory tests
└── integration/    # moto tests — real DynamoDB/S3 queries
```

## Testing

```bash
.venv/bin/pytest tests/ -v        # full suite (25 tests, ~2s)
.venv/bin/pytest tests/domain/ -v  # pure unit tests
.venv/bin/pytest tests/integration/ -v  # moto integration tests
```

Tests use moto fixtures from `tests/conftest.py` — no real AWS calls needed.

## Sprint Plan

| Sprint | Status | Delivers |
|--------|--------|----------|
| **1** | ✅ Complete | Foundation + dynamic tool engine + /setup + CI |
| **2** | Next | Full /setup interview polish + proactive scheduling (protocol-driven EventBridge) |
| **3** | Planned | Compounds module + cycle tracking + `[name] arrived` command |
| **4** | Planned | Inline keyboards for one-tap logging + UX polish |

## Important Notes

- All times should be ET (Eastern Time). EventBridge cron rules use UTC.
- `apex.yaml` is gitignored — it lives on S3, never in the repo.
- `.notes/` is gitignored — contains internal architecture docs, ADRs, sprint notes.
- The `compounds` section in `apex.yaml` is fully optional. Remove it and all compound logic is skipped gracefully.
- `build_tools()` in `factory.py` is called at Lambda cold start. Adding a metric to the protocol creates new tools on next cold start — no deploy needed.
- State machine TTL: 10 minutes for most states, 30 minutes for `setup_in_progress`.
- DynamoDB TTL is enabled on the `ttl` attribute — state records auto-expire.
