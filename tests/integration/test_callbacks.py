from datetime import date, timedelta
from unittest.mock import patch

from apex.domain.dates import local_today
from apex.domain.models import Protocol


def _protocol(compounds: list[dict] | None = None) -> Protocol:
    return Protocol(**{
        "version": "2",
        "profile": {
            "name": "Alex",
            "goal": "recomp",
            "timezone": "America/New_York",
            "start_date": "2026-05-19",
        },
        "tracking": {"metrics": [{"name": "sleep", "type": "numeric"}]},
        "supplements": {
            "morning": [
                {"name": "Creatine", "dose": "5g"},
                {"name": "Omega-3", "dose": "2g"},
            ],
            "evening": [{"name": "Magnesium", "dose": "400mg"}],
        },
        "schedule": {},
        "compounds": compounds,
    })


def _on_cycle_compounds() -> list[dict]:
    start = (date.today() - timedelta(days=9)).isoformat()
    return [
        {
            "name": "BPC-157",
            "cycle": {"on_weeks": 8, "off_weeks": 4},
            "dosing": {"am": "250mcg"},
            "start_date": start,
        },
        {
            "name": "TB-500",
            "cycle": {"on_weeks": 6, "off_weeks": 6},
            "dosing": {"pm": "2mg"},
            "start_date": None,  # not started — must be excluded
        },
    ]


def _cq(data: str, message_id: int = 42) -> dict:
    return {
        "id": "cb-1",
        "data": data,
        "message": {"message_id": message_id, "chat": {"id": 999}},
    }


def _env(aws_env, compounds=None):
    from apex.infra.db import Repositories
    from apex.infra.storage import ProtocolStore
    repos = Repositories(table=aws_env["table"], user_id="999")
    store = ProtocolStore(bucket="apex-test-bucket")
    store.save(_protocol(compounds))
    return repos, store


def test_supps_all_writes_log(aws_env):
    from apex.handlers.callback import handle_callback
    repos, store = _env(aws_env)

    with patch("apex.handlers.callback.send") as mock_send, \
         patch("apex.handlers.callback.answer_callback"):
        handle_callback(_cq("supps:all"), repos=repos, store=store)

    logs = repos.logs.get_day(local_today("America/New_York").isoformat())
    assert len(logs) == 1
    assert logs[0]["metric"] == "supplements"
    assert logs[0]["value"] == 1
    mock_send.assert_called_once()


def test_supps_none_writes_zero(aws_env):
    from apex.handlers.callback import handle_callback
    repos, store = _env(aws_env)

    with patch("apex.handlers.callback.send"), \
         patch("apex.handlers.callback.answer_callback"):
        handle_callback(_cq("supps:none"), repos=repos, store=store)

    logs = repos.logs.get_day(local_today("America/New_York").isoformat())
    assert logs[0]["metric"] == "supplements"
    assert logs[0]["value"] == 0


def test_compounds_all_writes_log(aws_env):
    from apex.handlers.callback import handle_callback
    repos, store = _env(aws_env, compounds=_on_cycle_compounds())

    with patch("apex.handlers.callback.send") as mock_send, \
         patch("apex.handlers.callback.answer_callback"):
        handle_callback(_cq("compounds:all"), repos=repos, store=store)

    logs = repos.logs.get_day(local_today("America/New_York").isoformat())
    assert len(logs) == 1
    assert logs[0]["metric"] == "compounds"
    assert logs[0]["value"] == 1
    # Only the on-cycle compound counts
    assert "BPC-157" in logs[0].get("notes", "")
    assert "TB-500" not in logs[0].get("notes", "")
    mock_send.assert_called_once()


def test_supps_partial_start_sets_state_and_shows_chips(aws_env):
    from apex.handlers.callback import handle_callback
    repos, store = _env(aws_env)

    with patch("apex.handlers.callback.edit_message") as mock_edit, \
         patch("apex.handlers.callback.answer_callback"):
        handle_callback(_cq("supps:partial"), repos=repos, store=store)

    state, ctx = repos.users.get_state()
    assert state == "awaiting_partial_picks"
    assert ctx["flow"] == "supps"
    assert ctx["selected"] == []
    assert ctx["all_names"] == ["Creatine", "Omega-3"]
    mock_edit.assert_called_once()
    assert mock_edit.call_args[0][0] == 42


def test_toggle_updates_selected_list(aws_env):
    from apex.handlers.callback import handle_callback
    repos, store = _env(aws_env)
    repos.users.set_state(
        "awaiting_partial_picks",
        {"flow": "supps", "selected": [], "all_names": ["Creatine", "Omega-3"]},
    )

    with patch("apex.handlers.callback.edit_message") as mock_edit, \
         patch("apex.handlers.callback.answer_callback"):
        handle_callback(_cq("toggle:creatine"), repos=repos, store=store)

    _, ctx = repos.users.get_state()
    assert ctx["selected"] == ["Creatine"]
    mock_edit.assert_called_once()

    # Toggle again removes it
    with patch("apex.handlers.callback.edit_message"), \
         patch("apex.handlers.callback.answer_callback"):
        handle_callback(_cq("toggle:creatine"), repos=repos, store=store)

    _, ctx = repos.users.get_state()
    assert ctx["selected"] == []


def test_supps_partial_done_writes_fraction_and_clears_state(aws_env):
    from apex.handlers.callback import handle_callback
    repos, store = _env(aws_env)
    repos.users.set_state(
        "awaiting_partial_picks",
        {"flow": "supps", "selected": ["Creatine"], "all_names": ["Creatine", "Omega-3"]},
    )

    with patch("apex.handlers.callback.send") as mock_send, \
         patch("apex.handlers.callback.answer_callback"):
        handle_callback(_cq("supps:partial:done"), repos=repos, store=store)

    logs = repos.logs.get_day(local_today("America/New_York").isoformat())
    assert logs[0]["metric"] == "supplements"
    assert logs[0]["value"] == 0.5
    assert "Creatine" in logs[0].get("notes", "")
    state, _ = repos.users.get_state()
    assert state == "idle"
    mock_send.assert_called_once()


def test_unknown_callback_is_ignored(aws_env):
    from apex.handlers.callback import handle_callback
    repos, store = _env(aws_env)

    with patch("apex.handlers.callback.send") as mock_send, \
         patch("apex.handlers.callback.answer_callback"):
        handle_callback(_cq("bogus:data"), repos=repos, store=store)

    assert repos.logs.get_day(date.today().isoformat()) == []
    mock_send.assert_not_called()
