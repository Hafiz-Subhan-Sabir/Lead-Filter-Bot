import json
from pathlib import Path

from openai import OpenAI

from config import settings
from schemas import AIDecision, ExtractedFields, ProfileCreate
from services.contact_extract import extract_contacts_from_text

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "filter_system.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def build_user_prompt(profile: ProfileCreate, message: str, platform: str) -> str:
    flags = {
        "want_remote": profile.want_remote,
        "want_onsite": profile.want_onsite,
        "want_hiring": profile.want_hiring,
        "want_startups": profile.want_startups,
        "want_no_website": profile.want_no_website,
        "min_confidence": profile.min_confidence,
    }
    return f"""PLATFORM:
{platform}

USER INTENT:
{profile.intent}

PROFILE FLAGS:
{json.dumps(flags, indent=2)}

MESSAGE:
{message}

Return JSON with keys:
is_match, category, work_type, company_type, is_lead, has_website,
confidence, reason, extracted
"""


def _merge_contacts(decision: AIDecision, text: str) -> AIDecision:
    found = extract_contacts_from_text(text)
    ext = decision.extracted

    emails = list(dict.fromkeys([*(ext.emails or []), *(found.get("emails") or [])]))
    if ext.email and ext.email.lower() not in emails:
        emails.insert(0, ext.email.lower())
    if found.get("email") and found["email"] not in emails:
        emails.insert(0, found["email"])

    phones = list(dict.fromkeys([*(ext.phones or []), *(found.get("phones") or [])]))
    if ext.phone and ext.phone not in phones:
        phones.insert(0, ext.phone)
    if found.get("phone") and found["phone"] not in phones:
        phones.insert(0, found["phone"])

    website = ext.website or found.get("website")

    decision.extracted = ExtractedFields(
        role=ext.role,
        date_mentioned=ext.date_mentioned,
        hours_ago_estimate=ext.hours_ago_estimate,
        location=ext.location,
        company_name=ext.company_name,
        contact_name=ext.contact_name,
        uploader_name=ext.uploader_name or ext.contact_name,
        email=emails[0] if emails else None,
        phone=phones[0] if phones else None,
        website=website,
        notes=ext.notes,
        emails=emails,
        phones=phones,
    )
    return decision


def classify_message(
    profile: ProfileCreate,
    message: str,
    platform: str = "other",
) -> AIDecision:
    response = get_client().chat.completions.create(
        model=settings.openai_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_user_prompt(profile, message, platform),
            },
        ],
    )
    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    decision = AIDecision.model_validate(data)
    return _merge_contacts(decision, message)
