from datetime import datetime

from pydantic import BaseModel, Field


class GaokaoPlanRequest(BaseModel):
    province: str = Field(max_length=64)
    score: str = Field(max_length=32)
    rank: str | None = Field(default=None, max_length=32)
    subject_combination: str = Field(max_length=128)
    preferred_majors: str | None = Field(default=None, max_length=255)
    preferred_cities: str | None = Field(default=None, max_length=255)
    career_preferences: str | None = Field(default=None, max_length=255)
    family_budget: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=1000)
    advisor_mode: str | None = Field(default="hybrid", max_length=32)
    advisor_provider: str | None = Field(default=None, max_length=32)
    advisor_model: str | None = Field(default=None, max_length=128)


class GaokaoConsultationRequest(BaseModel):
    province: str = Field(default="吉林省", max_length=64)
    score: str | None = Field(default=None, max_length=32)
    rank: str | None = Field(default=None, max_length=32)
    subject_combination: str | None = Field(default=None, max_length=128)
    preferred_majors: str | None = Field(default=None, max_length=255)
    preferred_cities: str | None = Field(default=None, max_length=255)
    career_preferences: str | None = Field(default=None, max_length=255)
    family_budget: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=1000)


class GaokaoConsultQuestion(BaseModel):
    id: str
    field: str
    title: str
    question: str
    why: str
    placeholder: str | None = None
    required: bool = True
    suggested_options: list[str] = Field(default_factory=list)


class GaokaoConsultationResponse(BaseModel):
    readiness: str
    opening: str
    inferred_track: str | None = None
    quick_judgment: list[str] = Field(default_factory=list)
    questions: list[GaokaoConsultQuestion] = Field(default_factory=list)
    next_step: str


class GaokaoControlLineItem(BaseModel):
    line_type: str
    score: int


class GaokaoDirectionCard(BaseModel):
    title: str
    content: str


class GaokaoMajorProfile(BaseModel):
    major_name: str
    discipline: str | None = None
    major_category: str | None = None
    duration: str | None = None
    degree: str | None = None
    science_ratio: str | None = None
    training_goal: str | None = None
    overview: str | None = None
    employment_rate: str | None = None
    salary_after_5y: str | None = None
    salary_rank: str | None = None
    top_jobs: list[str] = Field(default_factory=list)
    career_paths: list[str] = Field(default_factory=list)
    sample_schools: list[str] = Field(default_factory=list)
    catalog_major_code: str | None = None
    catalog_level: str | None = None
    similar_majors: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    postgraduate_paths: list[str] = Field(default_factory=list)


class GaokaoRecommendation(BaseModel):
    school: str
    major: str
    city: str
    school_level: str | None = None
    bucket: str
    fit_score: int
    ranking_score: int | None = None
    ranking_reasons: list[str] = Field(default_factory=list)
    risk_level: str
    reason: str
    major_comment: str | None = None
    decision_tags: list[str] = Field(default_factory=list)
    data_year: int
    min_score: int
    min_rank: int | None = None
    plan_count: int | None = None
    year_span: str | None = None
    source_name: str | None = None


class GaokaoExtendedRecommendation(BaseModel):
    school: str
    major: str
    city: str
    school_level: str | None = None
    group: str
    fit_label: str
    reason: str
    decision_tags: list[str] = Field(default_factory=list)
    evidence_type: str | None = None
    evidence_label: str | None = None
    reference_year: int | None = None
    reference_score: int | None = None
    reference_rank: int | None = None
    source_name: str | None = None
    source_url: str | None = None


class GaokaoPlanResponse(BaseModel):
    plan_id: int
    province: str
    year: int
    track: str
    score: str
    rank: str | None = None
    calculated_rank: int
    subject_combination: str
    summary: str
    advisor_mode: str = "rules_only"
    advisor_provider: str | None = None
    advisor_model: str | None = None
    llm_enhanced: bool = False
    advisor_engine_note: str | None = None
    direction_advice: list[str] = Field(default_factory=list)
    direction_cards: list[GaokaoDirectionCard] = Field(default_factory=list)
    advisor_takeaways: list[str] = Field(default_factory=list)
    school_choice_logic: list[str] = Field(default_factory=list)
    major_observations: list[str] = Field(default_factory=list)
    major_profile: GaokaoMajorProfile | None = None
    major_breakdown: list[GaokaoDirectionCard] = Field(default_factory=list)
    signature_advice: list[str] = Field(default_factory=list)
    school_pool_note: str | None = None
    extended_pool: list[GaokaoExtendedRecommendation] = Field(default_factory=list)
    deep_analysis: list[str] = Field(default_factory=list)
    strategy: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    execution_checklist: list[str] = Field(default_factory=list)
    control_lines: list[GaokaoControlLineItem] = Field(default_factory=list)
    recommendations: list[GaokaoRecommendation] = Field(default_factory=list)
    created_at: datetime


class GaokaoPlanSummary(BaseModel):
    plan_id: int
    province: str
    score: str
    subject_combination: str
    summary: str
    created_at: datetime
