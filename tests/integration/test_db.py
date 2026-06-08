from datetime import date

from apex.infra.db import LogRepository, UserRepository

_TODAY = date.today().isoformat()


def test_log_write_and_read(ddb_table):
    repo = LogRepository(table=ddb_table, user_id="999")
    repo.write(metric="sleep", value=7.5, log_date=_TODAY)

    logs = repo.get_range(metric="sleep", days=7)
    assert len(logs) == 1
    assert logs[0]["value"] == 7.5
    assert logs[0]["metric"] == "sleep"


def test_log_multiple_metrics_same_day(ddb_table):
    repo = LogRepository(table=ddb_table, user_id="999")
    repo.write(metric="sleep", value=7.5, log_date=_TODAY)
    repo.write(metric="protein", value=180.0, log_date=_TODAY)

    logs = repo.get_day(date_str=_TODAY)
    found_metrics = {log["metric"] for log in logs}
    assert "sleep" in found_metrics
    assert "protein" in found_metrics


def test_log_notes_stored(ddb_table):
    repo = LogRepository(table=ddb_table, user_id="999")
    repo.write(metric="sleep", value=7.5, log_date=_TODAY, notes="felt rested")

    logs = repo.get_range(metric="sleep", days=7)
    assert logs[0].get("notes") == "felt rested"


def test_user_state_set_and_get(ddb_table):
    repo = UserRepository(table=ddb_table, user_id="999")
    repo.set_state("setup_in_progress", {"step": "goal"})

    state, ctx = repo.get_state()
    assert state == "setup_in_progress"
    assert ctx["step"] == "goal"


def test_user_state_returns_idle_when_missing(ddb_table):
    repo = UserRepository(table=ddb_table, user_id="999")
    state, ctx = repo.get_state()
    assert state == "idle"
    assert ctx == {}


def test_user_clear_state(ddb_table):
    repo = UserRepository(table=ddb_table, user_id="999")
    repo.set_state("awaiting_something", {"data": "x"})
    repo.clear_state()
    state, ctx = repo.get_state()
    assert state == "idle"
