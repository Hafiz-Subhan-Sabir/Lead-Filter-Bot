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
    # Soft filters applied after classification
    max_hours_ago: float | None = Field(
        default=None,
        description="Keep posts estimated within this many hours (6, 12, 24, ...)",
    )
    require_email: bool = False
    require_phone: bool = False
    require_name: bool = False


class ExtractedFields(BaseModel):
    role: str | None = None
    date_mentioned: str | None = None
    hours_ago_estimate: float | None = None
    location: str | None = None
    company_name: str | None = None
    contact_name: str | None = None
    uploader_name: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    notes: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)


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
    source: str = "paste"
    url: str | None = None
    is_match: bool
    category: str | None
    work_type: str | None
    company_type: str | None
    is_lead: bool
    confidence: float
    reason: str | None
    contact_name: str | None = None
    uploader_name: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    company_name: str | None = None
    role: str | None = None
    location: str | None = None
    hours_ago_estimate: float | None = None
    date_mentioned: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    has_contact: bool = False


class FilterResponse(BaseModel):
    total_items: int
    source: str = "paste"
    matches: list[ResultOut]
    rejected: list[ResultOut]
    filtered_out: int = 0
