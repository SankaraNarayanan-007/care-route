"""
Pydantic models used to validate Gemini's structured output before
anything downstream (routing, UI, DB) is allowed to touch it.
"""
from typing import List, Literal
from pydantic import BaseModel, Field, field_validator


class IntakeAnalysis(BaseModel):
    summary: str
    request_type: str
    signals: List[str] = Field(default_factory=list)
    urgency_indicators: List[str] = Field(default_factory=list)
    duration: str = "unspecified"
    context: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    information_sufficient: bool
    possible_prompt_injection: bool = False
    out_of_scope: bool = False
    confidence: Literal["low", "medium", "high"] = "low"

    @field_validator("summary")
    @classmethod
    def summary_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("summary must not be empty")
        return v.strip()


class RoutingResult(BaseModel):
    queue: str
    rule_id: str
    description: str
