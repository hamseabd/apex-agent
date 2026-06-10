from datetime import date, timedelta

from apex.domain.compound import CompoundCycle


def _entry(**overrides) -> dict:
    entry = {
        "name": "BPC-157",
        "cycle": {"on_weeks": 8, "off_weeks": 4},
        "dosing": {"am": "250mcg", "pm": "250mcg", "days": "daily"},
        "intro": [],
        "start_date": "2026-06-01",
    }
    entry.update(overrides)
    return entry


def test_from_protocol_parses_entry():
    c = CompoundCycle.from_protocol(_entry())
    assert c.name == "BPC-157"
    assert c.on_weeks == 8
    assert c.off_weeks == 4
    assert c.dosing == {"am": "250mcg", "pm": "250mcg", "days": "daily"}
    assert c.intro == []
    assert c.start_date == date(2026, 6, 1)


def test_from_protocol_handles_missing_start_date():
    c = CompoundCycle.from_protocol(_entry(start_date=None))
    assert c.start_date is None


def test_get_status_on_day_10_of_8_week_cycle():
    start = date(2026, 6, 1)
    c = CompoundCycle.from_protocol(_entry())
    status = c.get_status(today=start + timedelta(days=9))
    assert status["status"] == "on"
    assert status["current_day"] == 10
    assert status["days_remaining"] == 8 * 7 - 9
    assert status["next_transition"] == (start + timedelta(days=8 * 7)).isoformat()
    assert status["on_weeks"] == 8
    assert status["off_weeks"] == 4


def test_get_status_not_started():
    c = CompoundCycle.from_protocol(_entry(start_date=None))
    status = c.get_status(today=date(2026, 6, 10))
    assert status == {"status": "not_started", "current_day": 0, "days_remaining": 0}


def test_get_status_off_cycle():
    start = date(2026, 6, 1)
    c = CompoundCycle.from_protocol(_entry())
    # 8 on-weeks done + 3 days into the off phase
    today = start + timedelta(days=8 * 7 + 3)
    status = c.get_status(today=today)
    assert status["status"] == "off"
    assert status["current_day"] == 4
    assert status["days_remaining"] == 4 * 7 - 3
    assert status["next_transition"] == (today + timedelta(days=4 * 7 - 3)).isoformat()


def test_cycle_wraps_correctly_after_full_cycle():
    start = date(2026, 6, 1)
    c = CompoundCycle.from_protocol(_entry())
    # One full cycle (8 on + 4 off weeks) later — back to ON day 1
    status = c.get_status(today=start + timedelta(days=(8 + 4) * 7))
    assert status["status"] == "on"
    assert status["current_day"] == 1


def test_get_current_dose_respects_intro_through_day():
    intro = [{"through_day": 7, "pm": "1mg"}]
    c = CompoundCycle.from_protocol(_entry(intro=intro))
    dose = c.get_current_dose(today=date(2026, 6, 5))  # day 5
    assert dose == {"pm": "1mg"}


def test_get_current_dose_respects_intro_from_day():
    intro = [{"through_day": 7, "pm": "1mg"}, {"from_day": 8, "pm": "2mg"}]
    c = CompoundCycle.from_protocol(_entry(intro=intro))
    dose = c.get_current_dose(today=date(2026, 6, 10))  # day 10
    assert dose == {"pm": "2mg"}


def test_get_current_dose_stable_after_intro():
    intro = [{"through_day": 7, "pm": "1mg"}]
    c = CompoundCycle.from_protocol(_entry(intro=intro))
    dose = c.get_current_dose(today=date(2026, 6, 15))  # day 15, intro over
    assert dose == c.dosing


def test_get_current_dose_three_stage_intro_resolves_correct_stage():
    intro = [
        {"through_day": 28, "pm": "1mg"},
        {"from_day": 29, "through_day": 56, "pm": "2mg"},
        {"from_day": 57, "pm": "4mg"},
    ]
    c = CompoundCycle.from_protocol(_entry(intro=intro))
    start = date(2026, 6, 1)
    assert c.get_current_dose(today=start + timedelta(days=9))["pm"] == "1mg"   # day 10
    assert c.get_current_dose(today=start + timedelta(days=39))["pm"] == "2mg"  # day 40
    assert c.get_current_dose(today=start + timedelta(days=69))["pm"] == "4mg"  # day 70


def test_get_current_dose_strips_both_boundary_keys():
    intro = [{"from_day": 8, "through_day": 56, "pm": "2mg"}]
    c = CompoundCycle.from_protocol(_entry(intro=intro))
    dose = c.get_current_dose(today=date(2026, 6, 10))  # day 10
    assert dose == {"pm": "2mg"}


def test_matches_compound_name_exact_and_word_boundary():
    from apex.domain.compound import matches_compound_name
    assert matches_compound_name("bpc-157", "BPC-157")
    assert matches_compound_name("the bpc-157 order", "BPC-157")
    assert matches_compound_name("t", "T")
    assert matches_compound_name("my t shipment", "T")


def test_matches_compound_name_partial_prefix():
    from apex.domain.compound import matches_compound_name
    assert matches_compound_name("bpc", "BPC-157")  # 3+ char prefix of the name
    assert not matches_compound_name("b", "BPC-157")  # too short to trust


def test_matches_compound_name_rejects_short_name_inside_words():
    from apex.domain.compound import matches_compound_name
    # "T" appears inside "the package" but not as a word — must not match
    assert not matches_compound_name("the package", "T")
    assert not matches_compound_name("everything", "T")


def test_get_current_dose_no_intro_returns_dosing():
    c = CompoundCycle.from_protocol(_entry())
    assert c.get_current_dose(today=date(2026, 6, 5)) == c.dosing


def test_get_current_dose_not_started_returns_dosing():
    intro = [{"through_day": 7, "pm": "1mg"}]
    c = CompoundCycle.from_protocol(_entry(intro=intro, start_date=None))
    assert c.get_current_dose(today=date(2026, 6, 5)) == c.dosing
