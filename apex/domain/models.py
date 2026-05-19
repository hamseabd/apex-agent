from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class Metric(BaseModel):
    name: str
    type: Literal["numeric", "boolean", "scale", "text"] = "numeric"
    unit: Optional[str] = None
    daily_target: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    description: Optional[str] = None

    @property
    def unit_str(self) -> str:
        return f" {self.unit}" if self.unit else ""


class TrackingConfig(BaseModel):
    metrics: list[Metric] = Field(default_factory=list)


class Profile(BaseModel):
    name: str
    goal: str
    timezone: str = "America/New_York"
    start_date: str


class Supplement(BaseModel):
    name: str
    dose: str


class Supplements(BaseModel):
    morning: list[Supplement] = Field(default_factory=list)
    evening: list[Supplement] = Field(default_factory=list)


class Compound(BaseModel):
    name: str
    cycle: dict
    dosing: dict
    intro: list[dict] = Field(default_factory=list)
    start_date: Optional[str] = None


class ScheduleReminder(BaseModel):
    time: str
    job: str


class Schedule(BaseModel):
    morning_checkin: str = "07:00"
    reminders: list[ScheduleReminder] = Field(default_factory=list)


class Protocol(BaseModel):
    version: str = "2"
    profile: Profile
    tracking: TrackingConfig
    supplements: Optional[Supplements] = None
    compounds: Optional[list[Compound]] = None
    schedule: Schedule = Field(default_factory=Schedule)
