from sqlalchemy.orm import Session

from models import FilterProfile, FilterResult, RawItem
from schemas import AIDecision, ProfileCreate


def create_profile(db: Session, data: ProfileCreate) -> FilterProfile:
    profile = FilterProfile(**data.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_profile(db: Session, profile_id: int) -> FilterProfile | None:
    return db.get(FilterProfile, profile_id)


def save_item(db: Session, text: str, source: str = "paste") -> RawItem:
    item = RawItem(source=source, raw_text=text)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def save_result(
    db: Session,
    item: RawItem,
    profile: FilterProfile,
    decision: AIDecision,
) -> FilterResult:
    is_match = decision.is_match and decision.confidence >= profile.min_confidence

    result = FilterResult(
        item_id=item.id,
        profile_id=profile.id,
        is_match=is_match,
        category=decision.category,
        work_type=decision.work_type,
        company_type=decision.company_type,
        is_lead=decision.is_lead,
        has_website=decision.has_website,
        confidence=decision.confidence,
        reason=decision.reason,
        extracted_json=decision.extracted.model_dump_json(),
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result
