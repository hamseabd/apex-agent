import boto3
import moto
import pytest

from apex.domain.models import Protocol

_BUCKET = "apex-test-bucket"


@pytest.fixture
def s3_bucket():
    # Decorator-style mock ensures ProtocolStore's own boto3 client is always
    # captured inside the mock context, regardless of where it's instantiated.
    with moto.mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=_BUCKET)
        yield client


def _put_raw(client, body: str) -> None:
    client.put_object(Bucket=_BUCKET, Key="apex.yaml", Body=body.encode())


def _get_raw(client) -> str:
    return client.get_object(Bucket=_BUCKET, Key="apex.yaml")["Body"].read().decode()


_YAML_WITH_COMMENTS = """\
# My health protocol
version: "2"
profile:
  name: Alex
  goal: recomp  # main goal
  timezone: America/New_York
  start_date: "2026-05-19"
tracking:
  metrics:
    - name: sleep  # track this daily
      type: numeric
      unit: hours
schedule:
  morning_checkin: "07:00"
"""


def _sample_protocol() -> Protocol:
    return Protocol(**{
        "version": "2",
        "profile": {
            "name": "Alex",
            "goal": "recomp",
            "timezone": "America/New_York",
            "start_date": "2026-05-19",
        },
        "tracking": {
            "metrics": [
                {"name": "sleep", "type": "numeric", "unit": "hours"},
                {"name": "protein", "type": "numeric", "unit": "grams", "daily_target": 180},
            ]
        },
        "schedule": {"morning_checkin": "07:00", "reminders": []},
    })


def test_protocol_save_and_load(s3_bucket):
    from apex.infra.storage import ProtocolStore
    store = ProtocolStore(bucket="apex-test-bucket")

    original = _sample_protocol()
    store.save(original)

    loaded = store.load()
    assert loaded.profile.name == "Alex"
    assert loaded.tracking.metrics[0].name == "sleep"
    assert loaded.tracking.metrics[1].daily_target == 180


def test_exists_false_before_save(s3_bucket):
    from apex.infra.storage import ProtocolStore
    store = ProtocolStore(bucket="apex-test-bucket")
    assert store.exists() is False


def test_exists_true_after_save(s3_bucket):
    from apex.infra.storage import ProtocolStore
    store = ProtocolStore(bucket="apex-test-bucket")
    store.save(_sample_protocol())
    assert store.exists() is True


def test_protocol_round_trips_compounds(s3_bucket):
    from apex.infra.storage import ProtocolStore
    store = ProtocolStore(bucket=_BUCKET)

    protocol = Protocol(**{
        "version": "2",
        "profile": {"name": "Alex", "goal": "recomp", "timezone": "UTC", "start_date": "2026-05-19"},
        "tracking": {"metrics": []},
        "schedule": {},
        "compounds": [
            {
                "name": "BPC-157",
                "cycle": {"on_weeks": 8, "off_weeks": 4},
                "dosing": {"am": "250mcg", "pm": "250mcg"},
                "start_date": None,
            }
        ],
    })
    store.save(protocol)
    loaded = store.load()
    assert loaded.compounds is not None
    assert loaded.compounds[0].name == "BPC-157"
    assert loaded.compounds[0].start_date is None


# ---------------------------------------------------------------------------
# I4: start_date=None must be absent from the raw YAML (not stored as null)
# ---------------------------------------------------------------------------

def test_compounds_start_date_excluded_from_yaml(s3_bucket):
    from apex.infra.storage import ProtocolStore
    store = ProtocolStore(bucket=_BUCKET)

    protocol = Protocol(**{
        "version": "2",
        "profile": {"name": "Alex", "goal": "recomp", "timezone": "UTC", "start_date": "2026-05-19"},
        "tracking": {"metrics": []},
        "schedule": {},
        "compounds": [{"name": "BPC-157", "cycle": {}, "dosing": {}, "start_date": None}],
    })
    store.save(protocol)
    raw = _get_raw(s3_bucket)
    # profile.start_date IS expected — only the compound's start_date should be absent
    compound_section = raw[raw.index("compounds:"):]
    assert "start_date" not in compound_section, "compound start_date=None should be excluded by exclude_none=True"


# ---------------------------------------------------------------------------
# C1: each ProtocolStore must own its own YAML instance (not the module global)
# ---------------------------------------------------------------------------

def test_each_store_has_own_yaml_instance(s3_bucket):
    import apex.infra.storage as storage_mod
    from apex.infra.storage import ProtocolStore
    store_a = ProtocolStore(bucket=_BUCKET)
    store_b = ProtocolStore(bucket=_BUCKET)
    assert hasattr(store_a, "_yaml"), "ProtocolStore should own a _yaml instance"
    assert store_a._yaml is not store_b._yaml
    assert store_a._yaml is not getattr(storage_mod, "_yaml", None)


# ---------------------------------------------------------------------------
# C2: save() must preserve YAML comments that were in the file at load() time
# ---------------------------------------------------------------------------

def test_save_preserves_yaml_comments(s3_bucket):
    from apex.infra.storage import ProtocolStore
    _put_raw(s3_bucket, _YAML_WITH_COMMENTS)

    store = ProtocolStore(bucket=_BUCKET)
    protocol = store.load()
    store.save(protocol)

    raw = _get_raw(s3_bucket)
    assert "# My health protocol" in raw, "top-level comment stripped on save"
    assert "# main goal" in raw, "inline field comment stripped on save"
    assert "# track this daily" in raw, "inline list-item comment stripped on save"


# ---------------------------------------------------------------------------
# I1: load() must raise ProtocolNotFoundError (not a raw ClientError) when
#     apex.yaml does not exist
# ---------------------------------------------------------------------------

def test_load_raises_protocol_not_found_when_missing(s3_bucket):
    from apex.infra.storage import ProtocolStore, ProtocolNotFoundError
    store = ProtocolStore(bucket=_BUCKET)
    with pytest.raises(ProtocolNotFoundError):
        store.load()
