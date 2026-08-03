from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    name: str
    intent: str
    want_remote: bool = False
    want_onsite: bool = False
    want_hiring: bool = True
    want_startups: bool = False
    want_no_website: bool = False
    min_confidence: float = 0.7


class ProfileOut(ProfileCreate):
    id: int

    model_config = {"from_attributes": True}


class FilterRequest(BaseModel):
    text: str = Field(..., description="Paste many messages separated by blank lines")
    profile_id: int
    source: str = "paste"


class ExtractedFields(BaseModel):
    role: str | None = None
    date_mentioned: str | None = None
    location: str | None = None
    company_name: str | None = None
    notes: str | None = None


class AIDecision(BaseModel):
    is_match: bool
    category: str
    work_type: str
    company_type: str
    is_lead: bool
    has_website: bool | None = None
    confidence: float
    reason: str
    extracted: ExtractedFields


class ResultOut(BaseModel):
    item_id: int
    raw_text: str
    is_match: bool
    category: str | None
    work_type: str | None
    company_type: str | None
    is_lead: bool
    confidence: float
    reason: str | None


class FilterResponse(BaseModel):
    total_items: int
    matches: list[ResultOut]
    rejected: list[ResultOut]
