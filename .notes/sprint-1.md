# Sprint 1 — Scope & Done Criteria

## What Sprint 1 Delivers

A deployable Telegram bot where:
1. User clones, deploys, sends `/setup`
2. Bot asks: what's your goal, what do you track, any supplements, schedule, compounds?
3. User confirms -> `apex.yaml` saved to S3
4. Agent has `log_X` and `get_X_logs` tools for every metric the user defined
5. Morning checkin job fires at configured time
6. CI passes on every push

## What Sprint 1 Does NOT Include

- Full proactive scheduling (Sprint 2)
- Compound cycle tracking (Sprint 3)
- Inline keyboard buttons (Sprint 4)
- Evals (future)

## Tasks

- [x] Task 0: Project scaffold
- [x] Task 1: Domain models (Pydantic v2)
- [x] Task 2: Settings (pydantic-settings)
- [x] Task 3: Telemetry (Powertools)
- [x] Task 4: DynamoDB repository (moto tests)
- [x] Task 5: S3 protocol store (moto tests)
- [x] Task 6: Dynamic tool factory <- the headline feature
- [x] Task 7: Agent builder
- [x] Task 8: Telegram wrapper
- [x] Task 9: Lambda entrypoints + handlers
- [x] Task 10: Protocol template + Terraform

## Done Criteria

```bash
# Tests pass
pytest tests/ -v

# Tool factory verification
python -c "
from apex.domain.models import Protocol
from apex.tools.factory import build_tools
from unittest.mock import MagicMock
p = Protocol(**{
  'version':'2',
  'profile':{'name':'T','goal':'test','timezone':'UTC','start_date':'2026-05-19'},
  'tracking':{'metrics':[{'name':'sleep'},{'name':'hrv'},{'name':'meditation'}]},
  'schedule':{}
})
tools = build_tools(p, MagicMock())
print([t.__name__ for t in tools])
# Expected: log_sleep, get_sleep_logs, log_hrv, get_hrv_logs, log_meditation, get_meditation_logs + core tools
"

# No hardcoded metric names in business logic
grep -rn 'sleep\|protein\|water' apex/tools/ apex/handlers/ --include='*.py' | grep -v test | grep -v '#'
# Should be empty
```
