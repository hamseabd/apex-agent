from unittest.mock import patch
from apex.domain.models import Protocol


def _sample_protocol():
    return Protocol(**{
        "version": "2",
        "profile": {
            "name": "Alex",
            "goal": "recomp",
            "timezone": "America/New_York",
            "start_date": "2026-06-01",
        },
        "tracking": {
            "metrics": [
                {"name": "sleep", "type": "numeric", "unit": "hours", "daily_target": 8},
                {"name": "water", "type": "numeric", "unit": "oz", "daily_target": 100},
            ]
        },
        "schedule": {
            "morning_checkin": "07:00",
            "reminders": [
                {"time": "10:00", "job": "water_reminder"},
                {"time": "22:00", "job": "bedtime_prompt"},
            ],
        },
    })


def test_water_reminder_sends_without_protocol(s3_bucket):
    # Bucket exists but no protocol saved — falls back to default message
    with patch("apex.scheduler.jobs.send") as mock_send:
        from apex.scheduler.jobs import water_reminder
        water_reminder()
    mock_send.assert_called_once()
    assert "💧" in mock_send.call_args[0][0]


def test_weekly_summary_sends_with_protocol(s3_bucket, ddb_table):
    from apex.infra.storage import ProtocolStore
    from apex.infra.db import Repositories

    ProtocolStore(bucket="apex-test-bucket").save(_sample_protocol())
    Repositories(table=ddb_table, user_id="999").logs.write(
        metric="sleep", value=7.5, log_date="2026-06-01", notes=""
    )

    with patch("apex.scheduler.jobs.send") as mock_send:
        from apex.scheduler.jobs import weekly_summary
        weekly_summary()

    mock_send.assert_called_once()
    assert "sleep" in mock_send.call_args[0][0]


def test_run_reminders_dispatches_matching_hour(s3_bucket):
    from apex.infra.storage import ProtocolStore
    ProtocolStore(bucket="apex-test-bucket").save(_sample_protocol())

    with patch("apex.scheduler.jobs.send") as mock_send, \
         patch("apex.scheduler.jobs._current_utc_hour", return_value="10:"):
        from apex.scheduler.jobs import run_reminders
        run_reminders()

    mock_send.assert_called_once()
    assert "💧" in mock_send.call_args[0][0]


def test_missed_day_check_sends_when_no_logs(ddb_table):
    # DynamoDB table exists but has no logs for today
    with patch("apex.scheduler.jobs.send") as mock_send:
        from apex.scheduler.jobs import missed_day_check
        missed_day_check()
    mock_send.assert_called_once()
    assert "👀" in mock_send.call_args[0][0]
