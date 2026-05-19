from apex.domain.models import Protocol
from unittest.mock import MagicMock, patch


def _make_protocol(metric_names: list[str]) -> Protocol:
    return Protocol(**{
        "version": "2",
        "profile": {
            "name": "Alex",
            "goal": "recomp",
            "timezone": "America/New_York",
            "start_date": "2026-05-19",
        },
        "tracking": {
            "metrics": [{"name": n, "type": "numeric"} for n in metric_names]
        },
        "schedule": {},
    })


def test_factory_generates_log_and_read_tool_per_metric():
    from apex.tools.factory import build_tools
    repos = MagicMock()
    protocol = _make_protocol(["sleep", "protein", "water"])
    tools = build_tools(protocol, repos)
    tool_names = [t.__name__ for t in tools]

    assert "log_sleep" in tool_names
    assert "get_sleep_logs" in tool_names
    assert "log_protein" in tool_names
    assert "get_protein_logs" in tool_names
    assert "log_water" in tool_names
    assert "get_water_logs" in tool_names


def test_factory_no_compound_tools_when_no_compounds():
    from apex.tools.factory import build_tools
    repos = MagicMock()
    protocol = _make_protocol(["sleep"])
    tools = build_tools(protocol, repos)
    tool_names = [t.__name__ for t in tools]
    assert not any("compound" in n for n in tool_names)


def test_factory_correct_tool_count():
    from apex.tools.factory import build_tools
    from apex.tools.core import CORE_TOOLS
    repos = MagicMock()
    protocol = _make_protocol(["sleep", "protein"])
    tools = build_tools(protocol, repos)
    # 2 metrics × 2 tools + core tools
    assert len(tools) == 2 * 2 + len(CORE_TOOLS)


def test_log_tool_writes_to_repo():
    from apex.tools.factory import build_tools
    repos = MagicMock()
    protocol = _make_protocol(["sleep"])
    tools = build_tools(protocol, repos)

    log_sleep = next(t for t in tools if t.__name__ == "log_sleep")
    with patch("apex.tools.factory._today", return_value="2026-05-19"):
        result = log_sleep(value=7.5)

    repos.logs.write.assert_called_once_with(
        metric="sleep", value=7.5, log_date="2026-05-19", notes=""
    )
    assert "7.5" in result


def test_read_tool_queries_repo():
    from apex.tools.factory import build_tools
    repos = MagicMock()
    repos.logs.get_range.return_value = [
        {"GSI1SK": "2026-05-19", "value": 7.5, "metric": "sleep"}
    ]
    protocol = _make_protocol(["sleep"])
    tools = build_tools(protocol, repos)

    get_sleep = next(t for t in tools if t.__name__ == "get_sleep_logs")
    result = get_sleep(days=7)

    repos.logs.get_range.assert_called_once_with(metric="sleep", days=7)
    assert "7.5" in result


def test_metric_with_unit_shows_unit_in_confirmation():
    from apex.tools.factory import build_tools
    repos = MagicMock()
    protocol = Protocol(**{
        "version": "2",
        "profile": {"name": "Alex", "goal": "recomp", "timezone": "UTC", "start_date": "2026-05-19"},
        "tracking": {"metrics": [{"name": "sleep", "type": "numeric", "unit": "hours", "daily_target": 8}]},
        "schedule": {},
    })
    tools = build_tools(protocol, repos)
    log_sleep = next(t for t in tools if t.__name__ == "log_sleep")
    with patch("apex.tools.factory._today", return_value="2026-05-19"):
        result = log_sleep(value=7.5)
    assert "hours" in result
    assert "8" in result  # target shown
