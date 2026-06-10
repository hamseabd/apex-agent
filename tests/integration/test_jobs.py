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


def _compound_protocol(compounds: list[dict]) -> Protocol:
    return Protocol(**{**_sample_protocol().model_dump(), "compounds": compounds})


def _started(days_ago: int) -> str:
    from datetime import date, timedelta
    return (date.today() - timedelta(days=days_ago)).isoformat()


def test_morning_checkin_sends_supplement_keyboard(s3_bucket):
    from apex.infra.storage import ProtocolStore
    p = Protocol(**{
        **_sample_protocol().model_dump(),
        "supplements": {
            "morning": [{"name": "Creatine", "dose": "5g"}],
            "evening": [],
        },
    })
    ProtocolStore(bucket="apex-test-bucket").save(p)

    with patch("apex.scheduler.jobs.send") as mock_send, \
         patch("apex.infra.telegram.send_with_keyboard") as mock_kb:
        from apex.scheduler.jobs import morning_checkin
        morning_checkin()

    mock_send.assert_called_once()
    mock_kb.assert_called_once()
    text, keyboard = mock_kb.call_args[0]
    assert "supplements" in text.lower()
    assert keyboard["inline_keyboard"][0][0]["callback_data"] == "supps:all"


def test_morning_checkin_no_keyboard_without_supplements(s3_bucket):
    from apex.infra.storage import ProtocolStore
    ProtocolStore(bucket="apex-test-bucket").save(_sample_protocol())

    with patch("apex.scheduler.jobs.send") as mock_send, \
         patch("apex.infra.telegram.send_with_keyboard") as mock_kb:
        from apex.scheduler.jobs import morning_checkin
        morning_checkin()

    mock_send.assert_called_once()
    mock_kb.assert_not_called()


def test_morning_injection_reminder_sends_am_doses(s3_bucket):
    from apex.infra.storage import ProtocolStore
    ProtocolStore(bucket="apex-test-bucket").save(_compound_protocol([{
        "name": "BPC-157",
        "cycle": {"on_weeks": 8, "off_weeks": 4},
        "dosing": {"am": "250mcg"},
        "start_date": _started(9),
    }]))

    with patch("apex.scheduler.jobs.send") as mock_send:
        from apex.scheduler.jobs import morning_injection_reminder
        morning_injection_reminder()

    mock_send.assert_called_once()
    msg = mock_send.call_args[0][0]
    assert "BPC-157" in msg
    assert "250mcg" in msg


def test_morning_injection_reminder_silent_without_compounds(s3_bucket):
    from apex.infra.storage import ProtocolStore
    ProtocolStore(bucket="apex-test-bucket").save(_sample_protocol())

    with patch("apex.scheduler.jobs.send") as mock_send:
        from apex.scheduler.jobs import morning_injection_reminder
        morning_injection_reminder()

    mock_send.assert_not_called()


def test_morning_injection_reminder_skips_not_started(s3_bucket):
    from apex.infra.storage import ProtocolStore
    ProtocolStore(bucket="apex-test-bucket").save(_compound_protocol([{
        "name": "BPC-157",
        "cycle": {"on_weeks": 8, "off_weeks": 4},
        "dosing": {"am": "250mcg"},
        "start_date": None,
    }]))

    with patch("apex.scheduler.jobs.send") as mock_send:
        from apex.scheduler.jobs import morning_injection_reminder
        morning_injection_reminder()

    mock_send.assert_not_called()


def test_injection_reminder_sends_pm_doses(s3_bucket):
    from apex.infra.storage import ProtocolStore
    ProtocolStore(bucket="apex-test-bucket").save(_compound_protocol([{
        "name": "TB-500",
        "cycle": {"on_weeks": 6, "off_weeks": 6},
        "dosing": {"pm": "2mg"},
        "start_date": _started(4),
    }]))

    with patch("apex.infra.telegram.send_with_keyboard") as mock_kb:
        from apex.scheduler.jobs import injection_reminder
        injection_reminder()

    mock_kb.assert_called_once()
    msg, keyboard = mock_kb.call_args[0]
    assert "TB-500" in msg
    assert "2mg" in msg
    assert "day 5" in msg
    assert keyboard["inline_keyboard"][0][0]["callback_data"] == "compounds:all"


def test_injection_reminder_alerts_on_escalation_day(s3_bucket):
    from apex.infra.storage import ProtocolStore
    ProtocolStore(bucket="apex-test-bucket").save(_compound_protocol([{
        "name": "Retatrutide",
        "cycle": {"on_weeks": 12, "off_weeks": 4},
        "dosing": {"pm": "4mg"},
        "intro": [
            {"through_day": 7, "pm": "1mg"},
            {"from_day": 8, "pm": "2mg"},
        ],
        "start_date": _started(7),  # today is day 8 — escalation day
    }]))

    with patch("apex.infra.telegram.send_with_keyboard") as mock_kb:
        from apex.scheduler.jobs import injection_reminder
        injection_reminder()

    msg = mock_kb.call_args[0][0]
    assert "⚠️" in msg
    assert "dose change tonight" in msg
    assert "2mg" in msg


def test_injection_jobs_registered():
    from apex.scheduler.jobs import _REGISTRY
    assert "morning_injection_reminder" in _REGISTRY
    assert "injection_reminder" in _REGISTRY


def test_missed_day_check_sends_when_no_logs(ddb_table):
    # DynamoDB table exists but has no logs for today
    with patch("apex.scheduler.jobs.send") as mock_send:
        from apex.scheduler.jobs import missed_day_check
        missed_day_check()
    mock_send.assert_called_once()
    assert "👀" in mock_send.call_args[0][0]
