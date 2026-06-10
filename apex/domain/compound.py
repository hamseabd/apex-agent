from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


def matches_compound_name(text: str, name: str) -> bool:
    """Match user text against a compound name without substring false positives.

    Short names like "T" must only match as whole words — never inside
    unrelated words ("the package"). A partial prefix ("bpc" for "BPC-157")
    is accepted only when it's 3+ characters.
    """
    text_lower = text.lower().strip()
    name_lower = name.lower()
    if text_lower == name_lower:
        return True
    if re.search(rf"\b{re.escape(name_lower)}\b", text_lower):
        return True
    return len(text_lower) >= 3 and text_lower in name_lower


@dataclass
class CompoundCycle:
    name: str
    on_weeks: int
    off_weeks: int
    dosing: dict                          # {am: str, pm: str, days: str}
    intro: list[dict] = field(default_factory=list)  # [{through_day: N, ...}, {from_day: N, ...}]
    start_date: Optional[date] = None

    @classmethod
    def from_protocol(cls, entry: dict) -> "CompoundCycle":
        start_raw = entry.get("start_date")
        return cls(
            name=entry["name"],
            on_weeks=entry["cycle"]["on_weeks"],
            off_weeks=entry["cycle"]["off_weeks"],
            dosing=entry.get("dosing", {}),
            intro=entry.get("intro", []),
            start_date=date.fromisoformat(start_raw) if start_raw else None,
        )

    def get_status(self, today: Optional[date] = None) -> dict:
        if today is None:
            today = date.today()
        if self.start_date is None:
            return {"status": "not_started", "current_day": 0, "days_remaining": 0}

        total_days = (today - self.start_date).days
        cycle_days = self.on_weeks * 7
        off_days = self.off_weeks * 7
        full_cycle = cycle_days + off_days
        position = total_days % full_cycle

        if position < cycle_days:
            return {
                "status": "on",
                "current_day": position + 1,
                "days_remaining": cycle_days - position,
                "next_transition": (today + timedelta(days=cycle_days - position)).isoformat(),
                "on_weeks": self.on_weeks,
                "off_weeks": self.off_weeks,
            }
        else:
            off_position = position - cycle_days
            return {
                "status": "off",
                "current_day": off_position + 1,
                "days_remaining": off_days - off_position,
                "next_transition": (today + timedelta(days=off_days - off_position)).isoformat(),
                "on_weeks": self.on_weeks,
                "off_weeks": self.off_weeks,
            }

    def get_current_dose(self, today: Optional[date] = None) -> dict:
        """Return today's dose, respecting intro stage overrides."""
        if today is None:
            today = date.today()
        if not self.intro or self.start_date is None:
            return self.dosing

        day = (today - self.start_date).days + 1
        for stage in self.intro:
            through = stage.get("through_day")
            from_day = stage.get("from_day")
            if (from_day is None or day >= from_day) and (through is None or day <= through):
                return {k: v for k, v in stage.items() if k not in ("from_day", "through_day")}
        return self.dosing
