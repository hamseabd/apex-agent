from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from apex.settings import get_settings


def _get_table():
    s = get_settings()
    ddb = boto3.resource("dynamodb", region_name=s.aws_region)
    return ddb.Table(s.table_name)


def _encode(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_encode(v) for v in value]
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


class LogRepository:
    def __init__(self, table=None, user_id: str | None = None):
        self._table = table or _get_table()
        self._user_id = user_id or get_settings().telegram_chat_id

    def write(self, metric: str, value: float, log_date: str, notes: str = "") -> None:
        item: dict[str, Any] = {
            "PK": f"U#{self._user_id}",
            "SK": f"LOG#{log_date}#{metric}",
            "GSI1PK": f"U#{self._user_id}#{metric}",
            "GSI1SK": log_date,
            "metric": metric,
            "value": _encode(value),
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
        if notes:
            item["notes"] = notes
        self._table.put_item(Item=item)

    def get_day(self, date_str: str) -> list[dict]:
        resp = self._table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"U#{self._user_id}") &
                Key("SK").begins_with(f"LOG#{date_str}")
            ),
        )
        return [_decode(i) for i in resp.get("Items", [])]

    def get_range(self, metric: str, days: int = 7) -> list[dict]:
        today = date.today()
        start = (today - timedelta(days=days - 1)).isoformat()
        resp = self._table.query(
            IndexName="GSI1",
            KeyConditionExpression=(
                Key("GSI1PK").eq(f"U#{self._user_id}#{metric}") &
                Key("GSI1SK").gte(start)
            ),
            ScanIndexForward=False,
        )
        return [_decode(i) for i in resp.get("Items", [])]

    def get_latest(self, metric: str) -> dict | None:
        results = self.get_range(metric, days=30)
        return results[0] if results else None


class UserRepository:
    def __init__(self, table=None, user_id: str | None = None):
        self._table = table or _get_table()
        self._user_id = user_id or get_settings().telegram_chat_id

    def get_state(self) -> tuple[str, dict]:
        resp = self._table.get_item(
            Key={"PK": f"U#{self._user_id}", "SK": "#STATE"}
        )
        item = resp.get("Item")
        if not item:
            return "idle", {}
        ttl: Any = item.get("ttl", 0)
        now = int(datetime.now(timezone.utc).timestamp())
        if ttl and now > int(ttl):
            return "idle", {}
        return str(item.get("state", "idle")), _decode(item.get("context", {}))

    def set_state(self, state: str, context: dict, ttl_seconds: int = 600) -> None:
        now = int(datetime.now(timezone.utc).timestamp())
        self._table.put_item(Item={
            "PK": f"U#{self._user_id}",
            "SK": "#STATE",
            "state": state,
            "context": _encode(context),
            "ttl": now + ttl_seconds,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    def clear_state(self) -> None:
        self._table.delete_item(Key={"PK": f"U#{self._user_id}", "SK": "#STATE"})

    def get_profile(self) -> dict | None:
        resp = self._table.get_item(
            Key={"PK": f"U#{self._user_id}", "SK": "#PROFILE"}
        )
        return _decode(resp["Item"]) if "Item" in resp else None

    def save_profile(self, profile: dict) -> None:
        self._table.put_item(Item={
            "PK": f"U#{self._user_id}",
            "SK": "#PROFILE",
            **_encode(profile),
        })


class Repositories:
    """Dependency container — pass into agent, tools, and handlers."""
    def __init__(self, table=None, user_id: str | None = None):
        self.logs = LogRepository(table, user_id)
        self.users = UserRepository(table, user_id)
