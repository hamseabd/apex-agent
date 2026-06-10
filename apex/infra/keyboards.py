from __future__ import annotations

import re


def inline_choice(buttons: list[tuple[str, str]]) -> dict:
    """Single-row inline keyboard. buttons = [(label, callback_data), ...]"""
    return {"inline_keyboard": [[{"text": label, "callback_data": data} for label, data in buttons]]}


def multi_select_chips(items: list[tuple[str, str, bool]], done_data: str) -> dict:
    """Multi-select chips. items = [(label, key, is_selected), ...]. Done button last row."""
    rows = []
    row = []
    for label, key, selected in items:
        display = f"✓ {label}" if selected else label
        row.append({"text": display, "callback_data": f"toggle:{key}"})
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([{"text": "Done ✅", "callback_data": done_data}])
    return {"inline_keyboard": rows}


def supplement_check_keyboard() -> dict:
    return inline_choice([
        ("✅ All", "supps:all"),
        ("🟡 Some", "supps:partial"),
        ("❌ None", "supps:none"),
    ])


def compound_check_keyboard() -> dict:
    return inline_choice([
        ("✅ All", "compounds:all"),
        ("🟡 Partial", "compounds:partial"),
        ("❌ None", "compounds:none"),
    ])


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def supplement_partial_keyboard(selected: list[str], all_names: list[str]) -> dict:
    items = [(name, _slug(name), name in selected) for name in all_names]
    return multi_select_chips(items, done_data="supps:partial:done")


def compound_partial_keyboard(selected: list[str], all_names: list[str]) -> dict:
    items = [(name, _slug(name), name in selected) for name in all_names]
    return multi_select_chips(items, done_data="compounds:partial:done")
