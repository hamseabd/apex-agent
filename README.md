# Apex — Self-Hosted Health Accountability Bot

![Tests](https://github.com/hamseabd/apex-agent/actions/workflows/test.yml/badge.svg)

> A Telegram health coach that builds its own tools from your protocol. Protocol-driven. Claude-powered. Runs entirely on your AWS account.

## What it does

- **Tracks anything you define.** Sleep, protein, HRV, meditation — every metric in your `apex.yaml` protocol gets its own logging and history tools, generated at runtime.
- **Holds you accountable.** Proactive check-ins, protocol-driven reminders, missed-day nudges, weekly summaries, one-tap supplement and injection logging via inline keyboards.
- **Manages compound cycles.** Define any compound with on/off weeks and intro dosing stages. Say "BPC-157 arrived" and Apex starts the cycle, escalates doses on schedule, and tells you when to stop.

```
 Telegram ──▶ API Gateway ──▶ Lambda (webhook) ──▶ Strands Agent ──▶ Claude (Bedrock)
                                    │                    │
                                    │              tools built at
                                    │              cold start from
                                    ▼                    ▼
 EventBridge ─▶ Lambda (scheduler)  DynamoDB ◀──── apex.yaml (S3)
 (hourly tick)  reminders/summaries (single-table)  single source of truth
```

## The architecture

**Tools are generated from your protocol, not written in code.** At cold start, `apex/tools/factory.py` reads `apex.yaml` and builds a `log_X` and `get_X_logs` tool for every metric you track. Add `meditation` to your protocol and a `log_meditation` tool appears in the agent on the next invocation — zero code changes, zero deploys.

The same principle runs through everything: reminders fire from the schedule in your protocol, compound tools appear only if you define compounds, and the agent's entire capability surface is a projection of one YAML file on S3.

- **Domain isolation** — `apex/domain/` is pure Python + Pydantic v2. No AWS imports, testable without mocks.
- **Repository pattern + DI** — handlers never touch DynamoDB directly; a `Repositories` container is injected everywhere.
- **Thin Lambda adapters** — `lambda_webhook.py` and `lambda_scheduler.py` are ~20 lines each; all logic lives in `apex/`.
- **Single-table DynamoDB** — one table, PK/SK + one GSI, covers logs, streaks, profile, and state machine.
- **Real-AWS testing** — integration tests run against moto's in-process DynamoDB and S3, not MagicMock.

## Prerequisites

- A Telegram bot token (via [@BotFather](https://t.me/BotFather)) and your chat ID
- An AWS account with [Bedrock model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) enabled for Claude
- Locally: Terraform, Docker, AWS CLI (configured), Python 3.12

## Quick start

```bash
# 1. Clone
git clone https://github.com/hamseabd/apex-agent.git && cd apex-agent

# 2. Store Telegram credentials in SSM
./scripts/store_secrets.sh

# 3. Provision everything — Terraform apply, Docker build/push, webhook registration
./scripts/bootstrap.sh

# 4. In Telegram: send /setup
#    Apex interviews you and writes apex.yaml to S3.

# 5. Ship code changes later with
./scripts/deploy.sh
```

## Your protocol

`apex.yaml` lives on S3 — it is the single source of truth for everything the bot does. See [apex.example.yaml](apex.example.yaml) for a full template.

```yaml
tracking:
  metrics:
    - { name: sleep, type: numeric, unit: hours, daily_target: 8 }
    - { name: protein, type: numeric, unit: grams, daily_target: 180 }
supplements:
  morning: [{ name: Creatine, dose: 5g }]
compounds:                      # optional — delete the section to disable
  - name: BPC-157
    cycle: { on_weeks: 8, off_weeks: 4 }
    dosing: { am: 250mcg }
schedule:
  morning_checkin: "07:00"
  reminders:
    - { time: "21:00", job: injection_reminder }
```

Every metric generates tools. Supplements drive the morning one-tap keyboard. Compounds get cycle tracking, dose escalation, and reminders. The schedule drives EventBridge-dispatched jobs.

## Daily usage

| You say | What happens |
|---|---|
| "slept 7.5 hours" | `log_sleep(7.5)` — confirmation with progress bar |
| "ran 3 miles, drank 60oz" | Two tools fire in one turn |
| "how's my protein this week?" | Pulls real logs, shows the trend |
| "BPC-157 arrived" | Cycle activated — start date set, reminders begin |
| "update my protein target to 200" | Edits `apex.yaml` on S3, preserving comments |
| Tap ✅ on the morning keyboard | All supplements logged in one tap |
| `/setup` | AI-guided interview rebuilds your protocol |

## Running tests

```bash
pip install -e ".[dev]"
.venv/bin/pytest tests/ -v               # full suite
.venv/bin/pytest tests/domain/ -v        # pure unit tests — no mocks
.venv/bin/pytest tests/integration/ -v   # moto-backed DynamoDB/S3 tests
```

## Project structure

```
apex/
├── domain/         # Pure Python — Protocol models, compound cycle math
├── infra/          # AWS adapters — DynamoDB, S3, Telegram, keyboards, telemetry
├── tools/          # factory.py — the dynamic tool generator
├── handlers/       # message routing, /setup interview, inline-keyboard callbacks
├── scheduler/      # protocol-driven scheduled jobs
├── agent.py        # build_agent(protocol, repos, store) → Strands Agent
└── settings.py     # pydantic-settings
lambda_webhook.py   # thin adapter — Telegram → handlers
lambda_scheduler.py # thin adapter — EventBridge → jobs
terraform/          # all infra: Lambda, DynamoDB, S3, API Gateway, EventBridge, IAM
tests/              # domain (pure) / tools / integration (moto)
```

## Sprint roadmap

| Sprint | Delivers |
|---|---|
| 1 | Foundation — dynamic tool engine, `/setup` interview, CI |
| 2 | Proactive scheduling — hourly EventBridge tick, protocol-driven reminders, `update_protocol` tool |
| 3 | Compounds — cycle tracking, intro dosing, `[name] arrived` activation |
| 4 | Inline keyboards — one-tap logging, formatted responses |

## Teardown

```bash
cd terraform && terraform destroy
```

Removes everything: Lambda, DynamoDB, S3 bucket, API Gateway, EventBridge rules, IAM roles. Your only ongoing costs while running are Bedrock tokens and a few cents of Lambda/DynamoDB — there are no always-on servers.
