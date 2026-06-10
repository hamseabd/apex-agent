from apex.infra.keyboards import (
    compound_check_keyboard,
    compound_partial_keyboard,
    inline_choice,
    multi_select_chips,
    supplement_check_keyboard,
    supplement_partial_keyboard,
)


def test_inline_choice_shape():
    kb = inline_choice([("Yes", "yes:1"), ("No", "no:0")])
    assert kb == {
        "inline_keyboard": [[
            {"text": "Yes", "callback_data": "yes:1"},
            {"text": "No", "callback_data": "no:0"},
        ]]
    }


def test_multi_select_chips_marks_selected():
    kb = multi_select_chips(
        [("Creatine", "creatine", True), ("Omega-3", "omega_3", False)],
        done_data="supps:partial:done",
    )
    rows = kb["inline_keyboard"]
    assert rows[0][0] == {"text": "✓ Creatine", "callback_data": "toggle:creatine"}
    assert rows[0][1] == {"text": "Omega-3", "callback_data": "toggle:omega_3"}
    assert rows[-1] == [{"text": "Done ✅", "callback_data": "supps:partial:done"}]


def test_multi_select_chips_wraps_rows_of_three():
    items = [(f"S{i}", f"s{i}", False) for i in range(5)]
    kb = multi_select_chips(items, done_data="x:done")
    rows = kb["inline_keyboard"]
    assert len(rows) == 3  # 3 chips + 2 chips + done row
    assert len(rows[0]) == 3
    assert len(rows[1]) == 2


def test_supplement_check_keyboard():
    kb = supplement_check_keyboard()
    data = [b["callback_data"] for b in kb["inline_keyboard"][0]]
    assert data == ["supps:all", "supps:partial", "supps:none"]


def test_compound_check_keyboard():
    kb = compound_check_keyboard()
    data = [b["callback_data"] for b in kb["inline_keyboard"][0]]
    assert data == ["compounds:all", "compounds:partial", "compounds:none"]


def test_supplement_partial_keyboard():
    kb = supplement_partial_keyboard(selected=["Omega-3"], all_names=["Creatine", "Omega-3"])
    rows = kb["inline_keyboard"]
    assert rows[0][0] == {"text": "Creatine", "callback_data": "toggle:creatine"}
    assert rows[0][1] == {"text": "✓ Omega-3", "callback_data": "toggle:omega_3"}
    assert rows[-1] == [{"text": "Done ✅", "callback_data": "supps:partial:done"}]


def test_compound_partial_keyboard():
    kb = compound_partial_keyboard(selected=[], all_names=["BPC-157"])
    rows = kb["inline_keyboard"]
    assert rows[0][0] == {"text": "BPC-157", "callback_data": "toggle:bpc_157"}
    assert rows[-1] == [{"text": "Done ✅", "callback_data": "compounds:partial:done"}]
