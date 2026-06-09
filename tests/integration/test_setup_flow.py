from unittest.mock import patch


def _make_repos(ddb_table):
    from apex.infra.db import Repositories
    return Repositories(table=ddb_table, user_id="999")


def test_finalize_saves_protocol_to_s3(s3_bucket, ddb_table):
    from apex.handlers.setup import handle_setup_message
    from apex.infra.storage import ProtocolStore

    repos = _make_repos(ddb_table)
    protocol = {
        "goal": "body recomposition",
        "metrics": [{"name": "sleep"}, {"name": "protein"}, {"name": "water"}],
        "supplements": {"morning": [{"name": "Creatine", "dose": "5g"}], "evening": []},
        "schedule": {"morning_checkin": "07:00", "reminders": []},
        "compounds": None,
    }
    repos.users.set_state("setup_in_progress", {"step": "confirm", "protocol": protocol})

    with patch("apex.handlers.setup.send"):
        handle_setup_message(
            text="confirm",
            step="confirm",
            context={"step": "confirm", "protocol": protocol},
            repos=repos,
        )

    store = ProtocolStore(bucket="apex-test-bucket")
    loaded = store.load()
    assert loaded.profile.goal == "body recomposition"
    assert len(loaded.tracking.metrics) == 3


def test_finalize_normalizes_string_metrics(s3_bucket, ddb_table):
    from apex.handlers.setup import handle_setup_message
    from apex.infra.storage import ProtocolStore

    repos = _make_repos(ddb_table)
    protocol = {
        "goal": "improve sleep",
        "metrics": ["sleep", "protein"],
        "schedule": {"morning_checkin": "07:00", "reminders": []},
        "compounds": None,
    }
    repos.users.set_state("setup_in_progress", {"step": "confirm", "protocol": protocol})

    with patch("apex.handlers.setup.send"):
        handle_setup_message(
            text="confirm",
            step="confirm",
            context={"step": "confirm", "protocol": protocol},
            repos=repos,
        )

    store = ProtocolStore(bucket="apex-test-bucket")
    loaded = store.load()
    assert len(loaded.tracking.metrics) == 2
    assert loaded.tracking.metrics[0].name == "sleep"
    assert loaded.tracking.metrics[1].name == "protein"


def test_finalize_handles_null_compounds(s3_bucket, ddb_table):
    from apex.handlers.setup import handle_setup_message
    from apex.infra.storage import ProtocolStore

    repos = _make_repos(ddb_table)
    protocol = {
        "goal": "recomp",
        "metrics": ["sleep"],
        "schedule": {"morning_checkin": "07:00", "reminders": []},
        "compounds": None,
    }
    repos.users.set_state("setup_in_progress", {"step": "confirm", "protocol": protocol})

    with patch("apex.handlers.setup.send"):
        handle_setup_message(
            text="confirm",
            step="confirm",
            context={"step": "confirm", "protocol": protocol},
            repos=repos,
        )

    store = ProtocolStore(bucket="apex-test-bucket")
    loaded = store.load()
    assert loaded.compounds is None
