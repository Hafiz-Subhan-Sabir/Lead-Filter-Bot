from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE_RE = re.compile(
    r"(?:\+|00)?(?:\d[\s().-]?){8,15}\d",
)
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)


def extract_contacts_from_text(text: str) -> dict:
    """Deterministic contact extraction from pasted text (never invents)."""
    emails = sorted({m.group(0).lower() for m in _EMAIL_RE.finditer(text)})
    phones: list[str] = []
    for m in _PHONE_RE.finditer(text):
        raw = m.group(0).strip()
        digits = re.sub(r"\D", "", raw)
        # avoid catching years / short numbers / confidence-like values
        if 9 <= len(digits) <= 15:
            phones.append(re.sub(r"\s+", " ", raw))
    # unique preserve order
    seen = set()
    uniq_phones = []
    for p in phones:
        key = re.sub(r"\D", "", p)
        if key not in seen:
            seen.add(key)
            uniq_phones.append(p)

    urls = _URL_RE.findall(text)
    website = None
    for u in urls:
        if "linkedin.com" in u or "upwork.com" in u or "wa.me" in u:
            continue
        website = u
        break

    return {
        "email": emails[0] if emails else None,
        "emails": emails,
        "phone": uniq_phones[0] if uniq_phones else None,
        "phones": uniq_phones,
        "website": website,
    }
