from apex.domain.models import Metric, Protocol, Compound, Schedule


def test_metric_numeric_defaults():
    m = Metric(name="sleep", type="numeric", unit="hours", daily_target=8)
    assert m.name == "sleep"
    assert m.unit == "hours"
    assert m.daily_target == 8


def test_metric_scale_type():
    m = Metric(name="energy", type="scale", min=1, max=10)
    assert m.type == "scale"


def test_metric_unit_str_property():
    m = Metric(name="sleep", unit="hours")
    assert m.unit_str == " hours"
    m2 = Metric(name="energy")
    assert m2.unit_str == ""


def test_protocol_parses_tracking_metrics():
    data = {
        "version": "2",
        "profile": {"name": "Alex", "goal": "recomp", "timezone": "America/New_York", "start_date": "2026-05-19"},
        "tracking": {
            "metrics": [
                {"name": "sleep", "type": "numeric", "unit": "hours", "daily_target": 8},
                {"name": "protein", "type": "numeric", "unit": "grams", "daily_target": 180},
            ]
        },
        "schedule": {"morning_checkin": "07:00", "reminders": []},
    }
    protocol = Protocol(**data)
    assert len(protocol.tracking.metrics) == 2
    assert protocol.tracking.metrics[0].name == "sleep"
    assert protocol.tracking.metrics[1].name == "protein"


def test_protocol_no_compounds_is_none():
    data = {
        "version": "2",
        "profile": {"name": "Alex", "goal": "recomp", "timezone": "America/New_York", "start_date": "2026-05-19"},
        "tracking": {"metrics": [{"name": "sleep"}]},
        "schedule": {},
    }
    p = Protocol(**data)
    assert p.compounds is None


def test_protocol_no_supplements_is_none():
    data = {
        "version": "2",
        "profile": {"name": "Alex", "goal": "recomp", "timezone": "America/New_York", "start_date": "2026-05-19"},
        "tracking": {"metrics": []},
        "schedule": {},
    }
    p = Protocol(**data)
    assert p.supplements is None


def test_compound_start_date_none_by_default():
    c = Compound(
        name="BPC-157",
        cycle={"on_weeks": 8, "off_weeks": 4},
        dosing={"am": "250mcg", "pm": "250mcg"},
    )
    assert c.start_date is None
    assert c.intro == []
