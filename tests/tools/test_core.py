from unittest.mock import MagicMock


def _make_protocol():
    from apex.domain.models import Protocol
    return Protocol(**{
        "version": "2",
        "profile": {
            "name": "Alex",
            "goal": "recomp",
            "timezone": "America/New_York",
            "start_date": "2026-06-01",
        },
        "tracking": {"metrics": [{"name": "sleep", "type": "numeric", "unit": "hours"}]},
        "schedule": {"morning_checkin": "07:00", "reminders": []},
    })


def test_update_protocol_string_field(s3_bucket):
    from apex.infra.storage import ProtocolStore
    from apex.tools.core import build_core_tools

    store = ProtocolStore(bucket="apex-test-bucket")
    store.save(_make_protocol())

    tools = build_core_tools(repos=MagicMock(), store=store)
    update = next(t for t in tools if t.__name__ == "update_protocol")

    result = update(field_path="schedule.morning_checkin", value="08:00")

    assert "✅" in result
    assert "08:00" in result
    assert store.load().schedule.morning_checkin == "08:00"


def _make_targeted_protocol():
    from apex.domain.models import Protocol
    return Protocol(**{
        "version": "2",
        "profile": {
            "name": "Alex",
            "goal": "recomp",
            "timezone": "America/New_York",
            "start_date": "2026-06-01",
        },
        "tracking": {"metrics": [
            {"name": "sleep", "type": "numeric", "unit": "hours", "daily_target": 8, "category": "recovery"},
            {"name": "protein", "type": "numeric", "unit": "g", "daily_target": 180, "category": "nutrition"},
        ]},
        "schedule": {},
    })


def test_get_today_status_shows_progress_bars(s3_bucket):
    from apex.infra.storage import ProtocolStore
    from apex.tools.core import build_core_tools

    store = ProtocolStore(bucket="apex-test-bucket")
    store.save(_make_targeted_protocol())
    repos = MagicMock()
    repos.logs.get_day.return_value = [{"metric": "sleep", "value": 7.5}]

    tools = build_core_tools(repos=repos, store=store)
    status = next(t for t in tools if t.__name__ == "get_today_status")
    result = status()

    assert "7.5/8" in result
    assert "94%" in result
    assert "█" in result


def test_get_today_status_groups_by_category(s3_bucket):
    from apex.infra.storage import ProtocolStore
    from apex.tools.core import build_core_tools

    store = ProtocolStore(bucket="apex-test-bucket")
    store.save(_make_targeted_protocol())
    repos = MagicMock()
    repos.logs.get_day.return_value = [
        {"metric": "sleep", "value": 7.5},
        {"metric": "protein", "value": 150},
        {"metric": "compounds", "value": 1},  # not in tracking — falls under Other
    ]

    tools = build_core_tools(repos=repos, store=store)
    status = next(t for t in tools if t.__name__ == "get_today_status")
    result = status()

    assert "Recovery" in result
    assert "Nutrition" in result
    assert "Other" in result
    assert result.index("Recovery") < result.index("sleep")
    assert result.index("Nutrition") < result.index("protein")


def test_get_today_status_empty(s3_bucket):
    from apex.infra.storage import ProtocolStore
    from apex.tools.core import build_core_tools

    store = ProtocolStore(bucket="apex-test-bucket")
    store.save(_make_targeted_protocol())
    repos = MagicMock()
    repos.logs.get_day.return_value = []

    tools = build_core_tools(repos=repos, store=store)
    status = next(t for t in tools if t.__name__ == "get_today_status")
    assert status() == "Nothing logged yet today."


def test_update_protocol_nonexistent_path_returns_error(s3_bucket):
    from apex.infra.storage import ProtocolStore
    from apex.tools.core import build_core_tools

    store = ProtocolStore(bucket="apex-test-bucket")
    store.save(_make_protocol())

    tools = build_core_tools(repos=MagicMock(), store=store)
    update = next(t for t in tools if t.__name__ == "update_protocol")

    result = update(field_path="profile.nonexistent_field", value="x")
    assert "Error" in result
