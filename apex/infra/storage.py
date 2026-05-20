from __future__ import annotations
from io import BytesIO

import boto3
from botocore.exceptions import ClientError
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from apex.domain.models import Protocol
from apex.settings import get_settings

_PROTOCOL_KEY = "apex.yaml"


class ProtocolNotFoundError(Exception):
    """Raised when apex.yaml does not exist in S3."""


def _deep_update(target: CommentedMap, source: dict) -> None:
    """Update a CommentedMap in-place from a plain dict, preserving comments on unchanged keys.

    Keys present in target but absent from source are left untouched so that
    manually-added YAML fields survive a save() round-trip.
    """
    for key, value in source.items():
        if key in target:
            if isinstance(value, dict) and isinstance(target[key], CommentedMap):
                _deep_update(target[key], value)
            elif isinstance(value, list) and isinstance(target[key], CommentedSeq):
                _update_seq(target[key], value)
            else:
                target[key] = value
        else:
            target[key] = value


def _update_seq(target: CommentedSeq, source: list) -> None:
    """Update a CommentedSeq in-place, preserving per-item comments where possible."""
    for i, item in enumerate(source):
        if i < len(target):
            if isinstance(item, dict) and isinstance(target[i], CommentedMap):
                _deep_update(target[i], item)
            else:
                target[i] = item
        else:
            target.append(item)
    while len(target) > len(source):
        target.pop()


class ProtocolStore:
    def __init__(self, bucket: str | None = None, region: str | None = None):
        s = get_settings()
        self._bucket = bucket or s.config_bucket
        self._client = boto3.client("s3", region_name=region or s.aws_region)
        # Per-instance YAML object — ruamel carries state during parse/dump
        self._yaml = YAML()
        self._yaml.preserve_quotes = True
        self._commented_map: CommentedMap | None = None

    def exists(self) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=_PROTOCOL_KEY)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise

    def load(self) -> Protocol:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=_PROTOCOL_KEY)
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NoSuchBucket"):
                raise ProtocolNotFoundError() from e
            raise
        content = response["Body"].read().decode("utf-8")
        self._commented_map = self._yaml.load(content)
        return Protocol(**self._commented_map)

    def save(self, protocol: Protocol) -> None:
        data = protocol.model_dump(exclude_none=True)
        if self._commented_map is not None:
            # Update in-place to preserve comments from the last load()
            _deep_update(self._commented_map, data)
            target = self._commented_map
        else:
            target = data
        buf = BytesIO()
        self._yaml.dump(target, buf)
        self._client.put_object(
            Bucket=self._bucket,
            Key=_PROTOCOL_KEY,
            Body=buf.getvalue(),
            ContentType="application/x-yaml",
        )
