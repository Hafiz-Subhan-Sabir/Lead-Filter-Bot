from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import AIDecision, FilterRequest, FilterResponse, ProfileCreate, ResultOut
from services import storage
from services.ai_filter import classify_message
from services.platform_detect import resolve_item_platform
from services.splitter import ParsedItem, split_into_items

router = APIRouter(prefix="/filter", tags=["filter"])


def decision_to_result(
    item_id: int,
    raw_text: str,
    source: str,
    url: str | None,
    decision: AIDecision,
    is_match: bool,
    hours_hint: float | None = None,
) -> ResultOut:
    ext = decision.extracted
    hours = ext.hours_ago_estimate if ext.hours_ago_estimate is not None else hours_hint
    email = ext.email
    phone = ext.phone
    name = ext.contact_name or ext.uploader_name
    has_contact = bool(email or phone or name)
    return ResultOut(
        item_id=item_id,
        raw_text=raw_text,
        source=source,
        url=url,
        is_match=is_match,
        category=decision.category,
        work_type=decision.work_type,
        company_type=decision.company_type,
        is_lead=decision.is_lead,
        confidence=decision.confidence,
        reason=decision.reason,
        genuine_score=decision.genuine_score,
        contact_name=ext.contact_name,
        uploader_name=ext.uploader_name,
        email=email,
        phone=phone,
        website=ext.website,
        company_name=ext.company_name,
        role=ext.role,
        location=ext.location,
        hours_ago_estimate=hours,
        date_mentioned=ext.date_mentioned,
        emails=ext.emails or ([email] if email else []),
        phones=ext.phones or ([phone] if phone else []),
        has_contact=has_contact,
    )


def passes_soft_filters(body: FilterRequest, out: ResultOut) -> bool:
    if body.max_hours_ago is not None:
        if out.hours_ago_estimate is None:
            return False
        if out.hours_ago_estimate > body.max_hours_ago:
            return False
    if body.require_email and not out.email:
        return False
    if body.require_phone and not out.phone:
        return False
    if body.require_name and not (out.contact_name or out.uploader_name):
        return False
    return True


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

    chunks: list[ParsedItem] = split_into_items(body.text)
    if not chunks:
        raise HTTPException(status_code=400, detail="No valid posts found in paste text")

    matches: list[ResultOut] = []
    rejected: list[ResultOut] = []
    filtered_out = 0

    for chunk in chunks:
        item_platform = resolve_item_platform(body.source, chunk.url)
        item = storage.save_item(
            db,
            chunk.text,
            source=item_platform,
            url=chunk.url,
        )
        decision = classify_message(profile_data, chunk.text, platform=item_platform)
        if chunk.hours_ago_hint is not None and decision.extracted.hours_ago_estimate is None:
            decision.extracted.hours_ago_estimate = chunk.hours_ago_hint

        result = storage.save_result(db, item, profile, decision)
        out = decision_to_result(
            item_id=item.id,
            raw_text=item.raw_text,
            source=item.source,
            url=item.url,
            decision=decision,
            is_match=result.is_match,
            hours_hint=chunk.hours_ago_hint,
        )

        if not passes_soft_filters(body, out):
            filtered_out += 1
            # still keep in rejected list so UI isn't empty / confusing
            out.is_match = False
            if out.reason and "filtered" not in out.reason.lower():
                out.reason = f"{out.reason} (removed by time/contact filters)"
            else:
                out.reason = "Removed by time/contact filters"
            rejected.append(out)
            continue

        if result.is_match:
            matches.append(out)
        else:
            rejected.append(out)

    # Sort matches by genuine_score then confidence
    matches.sort(key=lambda r: (r.genuine_score, r.confidence), reverse=True)

    return FilterResponse(
        total_items=len(chunks),
        source=body.source,
        matches=matches,
        rejected=rejected,
        filtered_out=filtered_out,
    )
