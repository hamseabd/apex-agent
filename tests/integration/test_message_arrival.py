from unittest.mock import MagicMock, patch

from apex.domain.dates import local_today
from apex.domain.models import Protocol


def _protocol(compounds: list[dict] | None) -> Protocol:
    return Protocol(**{
        "version": "2",
        "profile": {
            "name": "Alex",
            "goal": "recomp",
            "timezone": "America/New_York",
            "start_date": "2026-05-19",
        },
        "tracking": {"metrics": [{"name": "sleep", "type": "numeric"}]},
        "schedule": {},
        "compounds": compounds,
    })


def _compounds() -> list[dict]:
    return [
        {
            "name": "BPC-157",
            "cycle": {"on_weeks": 8, "off_weeks": 4},
            "dosing": {"am": "250mcg"},
            "start_date": None,
        },
        {
            "name": "TB-500",
            "cycle": {"on_weeks": 6, "off_weeks": 6},
            "dosing": {"pm": "2mg"},
            "start_date": None,
        },
    ]


def _idle_repos() -> MagicMock:
    repos = MagicMock()
    repos.users.get_state.return_value = ("idle", {})
    return repos


def test_is_compound_arrival_matches_name():
    from apex.handlers.message import _is_compound_arrival
    protocol = _protocol(_compounds())
    assert _is_compound_arrival("BPC-157 arrived", protocol)
    assert _is_compound_arrival("bpc arrived", protocol)
    assert _is_compound_arrival("tb-500 arrived", protocol)


def test_is_compound_arrival_rejects_non_arrival():
    from apex.handlers.message import _is_compound_arrival
    protocol = _protocol(_compounds())
    assert not _is_compound_arrival("slept 8 hours", protocol)
    assert not _is_compound_arrival("BPC-157 is great", protocol)


def test_is_compound_arrival_false_without_compounds():
    from apex.handlers.message import _is_compound_arrival
    assert not _is_compound_arrival("BPC-157 arrived", _protocol(None))


def test_arrival_activates_compound_and_sends(s3_bucket):
    from apex.infra.storage import ProtocolStore
    from apex.handlers.message import handle

    store = ProtocolStore(bucket="apex-test-bucket")
    store.save(_protocol(_compounds()))

    with patch("apex.infra.telegram.send") as mock_send:
        handle(text="BPC-157 arrived", agent=None, repos=_idle_repos(), store=store)

    saved = ProtocolStore(bucket="apex-test-bucket").load()
    assert saved.compounds[0].start_date == local_today("America/New_York").isoformat()
    assert saved.compounds[1].start_date is None
    mock_send.assert_called_once()
    msg = mock_send.call_args[0][0]
    assert "activated" in msg
    assert "BPC-157" in msg


def test_arrival_all_keyword_activates_everything(s3_bucket):
    from apex.infra.storage import ProtocolStore
    from apex.handlers.message import handle

    store = ProtocolStore(bucket="apex-test-bucket")
    store.save(_protocol(_compounds()))

    with patch("apex.infra.telegram.send") as mock_send:
        handle(text="all arrived", agent=None, repos=_idle_repos(), store=store)

    saved = ProtocolStore(bucket="apex-test-bucket").load()
    assert all(c.start_date == local_today("America/New_York").isoformat() for c in saved.compounds)
    msg = mock_send.call_args[0][0]
    assert "BPC-157" in msg
    assert "TB-500" in msg


def test_non_arrival_message_falls_through_to_agent(s3_bucket):
    from apex.infra.storage import ProtocolStore
    from apex.handlers.message import handle

    store = ProtocolStore(bucket="apex-test-bucket")
    store.save(_protocol(_compounds()))

    agent = MagicMock(return_value="logged it")
    with patch("apex.handlers.message.send") as mock_send:
        handle(text="slept 8 hours", agent=agent, repos=_idle_repos(), store=store)

    agent.assert_called_once_with("slept 8 hours")
    mock_send.assert_called_once_with("logged it")


def test_is_compound_arrival_short_name_needs_word_boundary():
    from apex.handlers.message import _is_compound_arrival
    protocol = _protocol([{
        "name": "T",
        "cycle": {"on_weeks": 12, "off_weeks": 4},
        "dosing": {"am": "100mg"},
        "start_date": None,
    }])
    # "t" is inside "the package" but not a word — must not hijack the message
    assert not _is_compound_arrival("the package arrived", protocol)
    assert _is_compound_arrival("T arrived", protocol)


def test_handle_works_without_store():
    from apex.handlers.message import handle
    agent = MagicMock(return_value="ok")
    with patch("apex.handlers.message.send"):
        handle(text="hello", agent=agent, repos=_idle_repos())
    agent.assert_called_once_with("hello")
