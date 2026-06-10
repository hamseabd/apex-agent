from datetime import date, timedelta
from unittest.mock import MagicMock

from apex.domain.models import Protocol


def _protocol(compounds: list[dict]) -> Protocol:
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


def _compound(**overrides) -> dict:
    entry = {
        "name": "BPC-157",
        "cycle": {"on_weeks": 8, "off_weeks": 4},
        "dosing": {"am": "250mcg"},
        "start_date": None,
    }
    entry.update(overrides)
    return entry


def test_build_compound_tools_returns_status_and_activate():
    from apex.tools.compound import build_compound_tools
    protocol = _protocol([_compound()])
    tools = build_compound_tools(protocol.compounds, MagicMock(), MagicMock())
    names = [t.__name__ for t in tools]
    assert "get_compound_status" in names
    assert "activate_compound" in names


def test_get_compound_status_not_started():
    from apex.tools.compound import build_compound_tools
    protocol = _protocol([_compound()])
    tools = build_compound_tools(protocol.compounds, MagicMock(), MagicMock())
    status = next(t for t in tools if t.__name__ == "get_compound_status")
    result = status()
    assert "BPC-157" in result
    assert "not started" in result
    assert "arrived" in result


def test_get_compound_status_on_cycle_shows_dose():
    from apex.tools.compound import build_compound_tools
    start = (date.today() - timedelta(days=9)).isoformat()
    protocol = _protocol([_compound(start_date=start)])
    tools = build_compound_tools(protocol.compounds, MagicMock(), MagicMock())
    status = next(t for t in tools if t.__name__ == "get_compound_status")
    result = status()
    assert "ON day 10" in result
    assert "250mcg" in result


def test_get_compound_status_no_compounds():
    from apex.tools.compound import build_compound_tools
    tools = build_compound_tools([], MagicMock(), MagicMock())
    status = next(t for t in tools if t.__name__ == "get_compound_status")
    assert status() == "No compounds configured."


def test_activate_compound_sets_start_date_and_saves():
    from apex.tools.compound import build_compound_tools
    protocol = _protocol([_compound()])
    store = MagicMock()
    store.load.return_value = protocol
    tools = build_compound_tools(protocol.compounds, MagicMock(), store)
    activate = next(t for t in tools if t.__name__ == "activate_compound")

    result = activate(name="bpc-157")  # case-insensitive

    store.save.assert_called_once()
    saved = store.save.call_args[0][0]
    assert saved.compounds[0].start_date == date.today().isoformat()
    assert "BPC-157" in result
    assert "✅" in result


def test_activate_compound_unknown_name():
    from apex.tools.compound import build_compound_tools
    protocol = _protocol([_compound()])
    store = MagicMock()
    store.load.return_value = protocol
    tools = build_compound_tools(protocol.compounds, MagicMock(), store)
    activate = next(t for t in tools if t.__name__ == "activate_compound")

    result = activate(name="unobtanium")

    store.save.assert_not_called()
    assert "not found" in result
    assert "BPC-157" in result


def test_factory_includes_compound_tools_without_store():
    # build_tools(protocol, MagicMock()) — store defaults to None, must not crash
    from apex.tools.factory import build_tools
    protocol = _protocol([_compound()])
    tools = build_tools(protocol, MagicMock())
    names = [t.__name__ for t in tools]
    assert "get_compound_status" in names
    assert "activate_compound" in names


def test_factory_passes_store_to_compound_tools():
    from apex.tools.factory import build_tools
    protocol = _protocol([_compound()])
    store = MagicMock()
    store.load.return_value = protocol
    tools = build_tools(protocol, MagicMock(), store)
    activate = next(t for t in tools if t.__name__ == "activate_compound")
    activate(name="BPC-157")
    store.save.assert_called_once()
