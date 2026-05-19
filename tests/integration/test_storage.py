import boto3
import moto
import pytest

from apex.domain.models import Protocol


@pytest.fixture
def s3_bucket(aws_credentials):
    with moto.mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="apex-test-bucket")
        yield client


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
    store = ProtocolStore(bucket="apex-test-bucket")

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
