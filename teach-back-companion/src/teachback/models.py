"""Care-plan schema. Plans are clinician-authored data; the software never edits them."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Severity = Literal["critical", "major", "minor"]
Kind = Literal["medication", "instruction", "warning", "appointment", "test"]
UNITS = {"mg", "per_day", "hours", "minutes", "days", "weeks", "pounds", "liters", "cups",
         "bpm", "fahrenheit", "celsius", "drinks"}


class Quantity(BaseModel):
    value: float
    unit: str

    @field_validator("unit")
    @classmethod
    def known_unit(cls, v: str) -> str:
        if v not in UNITS:
            raise ValueError(f"unknown unit {v!r}; expected one of {sorted(UNITS)}")
        return v


class Action(BaseModel):
    verbs: list[str]
    polarity: Literal["dont"] = "dont"
    objects: list[str] = Field(default_factory=list)  # if set, the verb only counts near one of these


class Misconception(BaseModel):
    id: str
    pattern: str
    message: str


class Fact(BaseModel):
    id: str
    severity: Severity
    statement: str
    concepts: list[list[str]] = Field(default_factory=list)
    quantities: list[Quantity] = Field(default_factory=list)
    action: Action | None = None
    emergency: bool = False
    coverage: Literal["concepts", "concepts_or_negated_action", "negated_action"] = "concepts"
    misconceptions: list[Misconception] = Field(default_factory=list)

    @model_validator(mode="after")
    def coverage_needs_action(self):
        if self.coverage != "concepts" and self.action is None:
            raise ValueError(f"fact {self.id}: coverage {self.coverage} requires an action")
        if self.coverage == "concepts" and not self.concepts and not self.quantities:
            raise ValueError(f"fact {self.id}: nothing to check")
        return self


class Appointment(BaseModel):
    with_: str = Field(alias="with")
    days_after_discharge: int
    time: str | None = None

    def when(self, discharge: date) -> datetime | None:
        day = discharge + timedelta(days=self.days_after_discharge)
        if not self.time:
            return datetime.combine(day, time(0, 0))
        return datetime.combine(day, time.fromisoformat(self.time))


class Task(BaseModel):
    type: Literal["daily", "appointment", "test"]
    label: str


class Item(BaseModel):
    id: str
    kind: Kind
    title: str
    original: str
    plain: str
    facts: list[Fact]
    drug_names: list[str] = Field(default_factory=list)
    education_topic: str | None = None
    appointment: Appointment | None = None
    task: Task | None = None


class Diagnosis(BaseModel):
    id: str
    name: str
    education_topic: str
    documented_note: str


class Patient(BaseModel):
    display_name: str
    age: int
    preferred_language: str


class Contact(BaseModel):
    role: str
    contact: str


class CarePlan(BaseModel):
    id: str
    synthetic: bool
    notice: str
    patient: Patient
    discharge_offset_days: int = 0
    care_team: list[Contact]
    diagnoses: list[Diagnosis]
    items: list[Item]

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [i.id for i in self.items] + [d.id for d in self.diagnoses]
        dupes = {x for x in ids if ids.count(x) > 1}
        if dupes:
            raise ValueError(f"duplicate ids in plan {self.id}: {sorted(dupes)}")
        fact_ids = [f.id for i in self.items for f in i.facts]
        dupes = {x for x in fact_ids if fact_ids.count(x) > 1}
        if dupes:
            raise ValueError(f"duplicate fact ids in plan {self.id}: {sorted(dupes)}")
        return self

    def item(self, item_id: str) -> Item:
        for i in self.items:
            if i.id == item_id:
                return i
        raise KeyError(item_id)

    def discharge_date(self, today: date | None = None) -> date:
        return (today or date.today()) + timedelta(days=self.discharge_offset_days)

    @property
    def drug_names(self) -> set[str]:
        return {n.lower() for i in self.items for n in i.drug_names}
