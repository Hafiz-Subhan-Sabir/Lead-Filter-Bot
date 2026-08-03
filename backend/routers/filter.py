from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import FilterRequest, FilterResponse, ProfileCreate, ResultOut
from services import storage
from services.ai_filter import classify_message
from services.splitter import split_into_items

router = APIRouter(prefix="/filter", tags=["filter"])


@router.post("/run", response_model=FilterResponse)
def run_filter(body: FilterRequest, db: Session = Depends(get_db)):
    profile = storage.get_profile(db, body.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile_data = ProfileCreate(
        name=profile.name,
        intent=profile.intent,
        want_remote=profile.want_remote,
        want_onsite=profile.want_onsite,
        want_hiring=profile.want_hiring,
        want_startups=profile.want_startups,
        want_no_website=profile.want_no_website,
        min_confidence=profile.min_confidence,
    )

    chunks = split_into_items(body.text)
    matches: list[ResultOut] = []
    rejected: list[ResultOut] = []

    for chunk in chunks:
        item = storage.save_item(db, chunk, source=body.source)
        decision = classify_message(profile_data, chunk)
        result = storage.save_result(db, item, profile, decision)

        out = ResultOut(
            item_id=item.id,
            raw_text=item.raw_text,
            is_match=result.is_match,
            category=result.category,
            work_type=result.work_type,
            company_type=result.company_type,
            is_lead=result.is_lead,
            confidence=result.confidence,
            reason=result.reason,
        )
        if result.is_match:
            matches.append(out)
        else:
            rejected.append(out)

    return FilterResponse(
        total_items=len(chunks),
        matches=matches,
        rejected=rejected,
    )
