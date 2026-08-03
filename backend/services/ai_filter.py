import json
from pathlib import Path

from openai import OpenAI

from config import settings
from schemas import AIDecision, ProfileCreate

client = OpenAI(api_key=settings.openai_api_key)

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "filter_system.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")


def build_user_prompt(profile: ProfileCreate, message: str) -> str:
    flags = {
        "want_remote": profile.want_remote,
        "want_onsite": profile.want_onsite,
        "want_hiring": profile.want_hiring,
        "want_startups": profile.want_startups,
        "want_no_website": profile.want_no_website,
        "min_confidence": profile.min_confidence,
    }
    return f"""USER INTENT:
{profile.intent}

PROFILE FLAGS:
{json.dumps(flags, indent=2)}

MESSAGE:
{message}

Return JSON with keys:
is_match, category, work_type, company_type, is_lead, has_website,
confidence, reason, extracted
"""


def classify_message(profile: ProfileCreate, message: str) -> AIDecision:
    response = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(profile, message)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    return AIDecision.model_validate(data)
