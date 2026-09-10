from typing import Literal

from pydantic import BaseModel, Field


class ImportRequest(BaseModel):
    input_text: str = Field(min_length=1)


class CollectionRequest(BaseModel):
    trigger: Literal["daily", "hourly", "manual", "recovery"] = "manual"
    item_ids: list[str] | None = None


class DecisionUpdate(BaseModel):
    decision_status: Literal["watching", "reviewing", "testing", "dropped", "scaling"]
    audience: str | None = None
    scenario: str | None = None
    problem: str | None = None
    delivery: str | None = None
    notes: str | None = None
    next_action: str | None = None
