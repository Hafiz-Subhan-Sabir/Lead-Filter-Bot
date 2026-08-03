from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


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
    max_hours_ago: float | None = None
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

    @field_validator("hours_ago_estimate", mode="before")
    @classmethod
    def coerce_hours(cls, v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    @field_validator(
        "role",
        "date_mentioned",
        "location",
        "company_name",
        "contact_name",
        "uploader_name",
        "email",
        "phone",
        "website",
        "notes",
        mode="before",
    )
    @classmethod
    def empty_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return str(v) if not isinstance(v, str) else v

    @field_validator("emails", "phones", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        if isinstance(v, list):
            return [str(x) for x in v if x]
        return []


class AIDecision(BaseModel):
    is_match: bool = False
    category: str = "other"
    work_type: str = "unknown"
    company_type: str = "unknown"
    is_lead: bool = False
    has_website: bool | None = None
    confidence: float = 0.0
    reason: str = ""
    extracted: ExtractedFields = Field(default_factory=ExtractedFields)
    genuine_score: float = 0.0

    @field_validator("category", "work_type", "company_type", "reason", mode="before")
    @classmethod
    def none_str_fields(cls, v, info):
        if v is None or v == "":
            defaults = {
                "category": "other",
                "work_type": "unknown",
                "company_type": "unknown",
                "reason": "",
            }
            return defaults.get(info.field_name, "")
        return str(v)

    @field_validator("confidence", "genuine_score", mode="before")
    @classmethod
    def coerce_float(cls, v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    @field_validator("is_match", "is_lead", mode="before")
    @classmethod
    def coerce_bool(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes"}
        return bool(v)

    @field_validator("has_website", mode="before")
    @classmethod
    def coerce_optional_bool(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes"}
        return bool(v)

    @model_validator(mode="before")
    @classmethod
    def ensure_extracted(cls, data):
        if not isinstance(data, dict):
            return data
        if data.get("extracted") is None:
            data["extracted"] = {}
        return data


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
    genuine_score: float = 0.0
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
