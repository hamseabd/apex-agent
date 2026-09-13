from __future__ import annotations

import boto3

from apex.settings import get_settings

_PREFIX = "knowledge/"


class KnowledgeStore:
    """Reads the health/research corpus from S3 (all objects under knowledge/)."""

    def __init__(self, bucket: str | None = None, region: str | None = None):
        s = get_settings()
        self._bucket = bucket or s.config_bucket
        self._client = boto3.client("s3", region_name=region or s.aws_region)

    def _list_keys(self) -> list[str]:
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=_PREFIX):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key != _PREFIX:  # skip the folder placeholder if present
                    keys.append(key)
        return sorted(keys)

    def exists(self) -> bool:
        return len(self._list_keys()) > 0

    def load_corpus(self) -> list[dict]:
        docs: list[dict] = []
        for key in self._list_keys():
            body = self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()
            docs.append(
                {
                    "source": key[len(_PREFIX) :],
                    "text": body.decode("utf-8"),
                }
            )
        return docs

    def total_tokens(self) -> int:
        """Rough token estimate (~4 chars/token) for the size guardrail."""
        return sum(len(d["text"]) for d in self.load_corpus()) // 4
