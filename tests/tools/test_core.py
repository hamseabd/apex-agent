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


def test_update_protocol_nonexistent_path_returns_error(s3_bucket):
    from apex.infra.storage import ProtocolStore
    from apex.tools.core import build_core_tools

    store = ProtocolStore(bucket="apex-test-bucket")
    store.save(_make_protocol())

    tools = build_core_tools(repos=MagicMock(), store=store)
    update = next(t for t in tools if t.__name__ == "update_protocol")

    result = update(field_path="profile.nonexistent_field", value="x")
    assert "Error" in result
