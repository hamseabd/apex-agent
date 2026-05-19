from __future__ import annotations
from io import StringIO

import boto3
from botocore.exceptions import ClientError
from ruamel.yaml import YAML

from apex.domain.models import Protocol
from apex.settings import get_settings

_PROTOCOL_KEY = "apex.yaml"
_yaml = YAML()
_yaml.preserve_quotes = True


class ProtocolStore:
    def __init__(self, bucket: str | None = None):
        s = get_settings()
        self._bucket = bucket or s.config_bucket
        self._client = boto3.client("s3", region_name=s.aws_region)

    def exists(self) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=_PROTOCOL_KEY)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise

    def load(self) -> Protocol:
        response = self._client.get_object(Bucket=self._bucket, Key=_PROTOCOL_KEY)
        content = response["Body"].read().decode("utf-8")
        data = _yaml.load(content)
        return Protocol(**data)

    def save(self, protocol: Protocol) -> None:
        buf = StringIO()
        _yaml.dump(protocol.model_dump(exclude_none=False), buf)
        self._client.put_object(
            Bucket=self._bucket,
            Key=_PROTOCOL_KEY,
            Body=buf.getvalue().encode("utf-8"),
        )
