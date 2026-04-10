from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DiagnosticCreateRequest(BaseModel):
    asset_id: int
    raw_text: str | None = Field(default=None, max_length=20000)


class DiagnosticResult(BaseModel):
    chapter: str | None = None
    confidence: float | None = None
    knowledge_weights: dict[str, float] = Field(default_factory=dict)
    top_matches: list[dict[str, Any]] = Field(default_factory=list)
    extracted_text_preview: str | None = None
    source: str | None = None


class DiagnosticTaskResponse(BaseModel):
    id: int
    asset_id: int
    status: str
    result: DiagnosticResult
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None
