import boto3
import moto
import pytest

from apex.infra.knowledge import KnowledgeStore


@pytest.fixture
def s3_bucket(aws_credentials):
    with moto.mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="apex-test-bucket")
        yield client


def _put(client, key, body):
    client.put_object(Bucket="apex-test-bucket", Key=key, Body=body.encode("utf-8"))


def test_exists_false_when_empty(s3_bucket):
    assert KnowledgeStore().exists() is False


def test_exists_true_with_doc(s3_bucket):
    _put(s3_bucket, "knowledge/creatine.md", "Creatine mono, 5g/day.")
    assert KnowledgeStore().exists() is True


def test_exists_ignores_non_knowledge_keys(s3_bucket):
    _put(s3_bucket, "apex.yaml", "version: '2'")
    assert KnowledgeStore().exists() is False


def test_load_corpus_returns_sorted_docs(s3_bucket):
    _put(s3_bucket, "knowledge/zinc.md", "Zinc doc.")
    _put(s3_bucket, "knowledge/creatine.md", "Creatine doc.")
    docs = KnowledgeStore().load_corpus()
    assert [d["source"] for d in docs] == ["creatine.md", "zinc.md"]
    assert docs[0]["text"] == "Creatine doc."


def test_load_corpus_empty(s3_bucket):
    assert KnowledgeStore().load_corpus() == []


def test_total_tokens_estimate(s3_bucket):
    _put(s3_bucket, "knowledge/a.md", "x" * 400)
    assert KnowledgeStore().total_tokens() == 100
