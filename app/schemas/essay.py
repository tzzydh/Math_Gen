from datetime import datetime

from pydantic import BaseModel, Field


class EssayCorrectionRequest(BaseModel):
    asset_id: int
    subject: str = Field(default="chinese", max_length=32)
    title: str | None = Field(default=None, max_length=100)
    raw_text: str | None = Field(default=None, max_length=20000)


class EssayCorrectionResponse(BaseModel):
    review_id: int
    asset_id: int
    subject: str
    source: str
    recognized_title: str | None = None
    recognized_text: str
    corrected_title: str
    corrected_text: str
    summary: str
    score: int
    score_max: int
    strengths: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    pdf_asset_id: int
    pdf_url: str


class EssayReviewSummary(BaseModel):
    review_id: int
    subject: str
    corrected_title: str
    score: int
    score_max: int
    created_at: datetime
    pdf_url: str


class EssayReviewDetail(EssayCorrectionResponse):
    created_at: datetime
