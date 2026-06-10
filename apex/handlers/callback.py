from __future__ import annotations
from datetime import date

from apex.infra.telegram import answer_callback, edit_message, send
from apex.infra.telemetry import logger, tracer


@tracer.capture_method
def handle_callback(callback_query: dict, repos=None, store=None) -> None:
    """Dispatch an inline keyboard callback by its callback_data."""
    if repos is None:
        from apex.infra.db import Repositories
        repos = Repositories()
    if store is None:
        from apex.infra.storage import ProtocolStore
        store = ProtocolStore()

    callback_id = callback_query["id"]
    data = callback_query.get("data", "")
    message_id = callback_query["message"]["message_id"]
    answer_callback(callback_id)

    if data == "supps:all":
        _handle_supps_all(repos, store)
    elif data == "supps:none":
        _handle_supps_none(repos)
    elif data == "supps:partial":
        _handle_supps_partial_start(message_id, repos, store)
    elif data == "supps:partial:done":
        _handle_partial_done(repos)
    elif data == "compounds:all":
        _handle_compounds_all(repos, store)
    elif data == "compounds:none":
        _handle_compounds_none(repos)
    elif data == "compounds:partial":
        _handle_compounds_partial_start(message_id, repos, store)
    elif data == "compounds:partial:done":
        _handle_partial_done(repos)
    elif data.startswith("toggle:"):
        _handle_toggle(data, message_id, repos)
    else:
        logger.warning(f"Unknown callback: {data}")


_FLOW_METRIC = {"supps": "supplements", "compounds": "peptides"}


def _morning_supplement_names(store) -> list[str]:
    protocol = store.load()
    if not protocol.supplements:
        return []
    return [s.name for s in protocol.supplements.morning]


def _on_cycle_compound_names(store) -> list[str]:
    from apex.domain.compound import CompoundCycle
    protocol = store.load()
    names = []
    for entry in protocol.compounds or []:
        c = CompoundCycle.from_protocol(entry.model_dump())
        if c.get_status()["status"] == "on":
            names.append(c.name)
    return names


def _write_log(repos, metric: str, value: float, notes: str = "") -> None:
    repos.logs.write(metric=metric, value=value, log_date=date.today().isoformat(), notes=notes)


def _handle_supps_all(repos, store) -> None:
    names = _morning_supplement_names(store)
    _write_log(repos, "supplements", 1, notes=", ".join(names))
    send(f"✅ Supplements logged — all {len(names)} taken.")


def _handle_supps_none(repos) -> None:
    _write_log(repos, "supplements", 0, notes="none taken")
    send("Logged — no supplements taken. Tomorrow's a new day.")


def _handle_compounds_all(repos, store) -> None:
    names = _on_cycle_compound_names(store)
    _write_log(repos, "peptides", 1, notes=", ".join(names))
    send(f"✅ Injections logged — all {len(names)} done.")


def _handle_compounds_none(repos) -> None:
    _write_log(repos, "peptides", 0, notes="none taken")
    send("Logged — no injections today.")


def _handle_supps_partial_start(message_id: int, repos, store) -> None:
    from apex.infra.keyboards import supplement_partial_keyboard
    names = _morning_supplement_names(store)
    repos.users.set_state(
        "awaiting_partial_picks",
        {"flow": "supps", "selected": [], "all_names": names},
    )
    edit_message(message_id, "Which supplements did you take?", supplement_partial_keyboard([], names))


def _handle_compounds_partial_start(message_id: int, repos, store) -> None:
    from apex.infra.keyboards import compound_partial_keyboard
    names = _on_cycle_compound_names(store)
    repos.users.set_state(
        "awaiting_partial_picks",
        {"flow": "compounds", "selected": [], "all_names": names},
    )
    edit_message(message_id, "Which injections did you do?", compound_partial_keyboard([], names))


def _handle_toggle(data: str, message_id: int, repos) -> None:
    from apex.infra.keyboards import _slug, compound_partial_keyboard, supplement_partial_keyboard
    state, ctx = repos.users.get_state()
    if state != "awaiting_partial_picks":
        logger.warning("Toggle received outside partial-pick flow")
        return
    key = data.split(":", 1)[1]
    selected = list(ctx.get("selected", []))
    all_names = ctx.get("all_names", [])
    name = next((n for n in all_names if _slug(n) == key), None)
    if name is None:
        return
    if name in selected:
        selected.remove(name)
    else:
        selected.append(name)
    repos.users.set_state("awaiting_partial_picks", {**ctx, "selected": selected})
    flow = ctx.get("flow", "supps")
    builder = supplement_partial_keyboard if flow == "supps" else compound_partial_keyboard
    prompt = "Which supplements did you take?" if flow == "supps" else "Which injections did you do?"
    edit_message(message_id, prompt, builder(selected, all_names))


def _handle_partial_done(repos) -> None:
    state, ctx = repos.users.get_state()
    if state != "awaiting_partial_picks":
        logger.warning("Partial done received outside partial-pick flow")
        return
    selected = ctx.get("selected", [])
    all_names = ctx.get("all_names", [])
    metric = _FLOW_METRIC.get(ctx.get("flow", "supps"), "supplements")
    value = round(len(selected) / len(all_names), 2) if all_names else 0
    _write_log(repos, metric, value, notes=", ".join(selected) or "none")
    repos.users.clear_state()
    send(f"✅ Logged {len(selected)}/{len(all_names)}: {', '.join(selected) or 'none'}.")
