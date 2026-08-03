from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from routers.filter import decision_to_result, passes_soft_filters
from schemas import FilterRequest, FilterResponse, ProfileCreate, ResultOut
from services import storage
from services.ai_filter import classify_message
from services.discover import discover_items, rerank_matches_with_ai
from services.splitter import ParsedItem, split_into_items

router = APIRouter(prefix="/discover", tags=["discover"])


class DiscoverRequest(BaseModel):
    profile_id: int
    source: str = "all"
    max_hours_ago: float | None = None
    require_email: bool = False
    require_phone: bool = False
    require_name: bool = False
    extra_text: str = ""
    max_results: int = Field(default=40, ge=5, le=60)
    deep: bool = True


@router.post("/run", response_model=FilterResponse)
def run_discover(body: DiscoverRequest, db: Session = Depends(get_db)):
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

    discovered = discover_items(profile.intent, body.source)
    chunks: list[ParsedItem] = [
        ParsedItem(text=d.text, url=d.url, hours_ago_hint=None) for d in discovered
    ]
    platforms = [d.source for d in discovered]

    if body.extra_text.strip():
        for extra in split_into_items(body.extra_text):
            chunks.append(extra)
            platforms.append(body.source if body.source != "all" else "other")

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail=(
                "No public posts found. Try a clearer intent, another platform, "
                "or add BRAVE_API_KEY / SERPAPI_KEY in .env for stronger search."
            ),
        )

    soft = FilterRequest(
        text="x",
        profile_id=body.profile_id,
        source=body.source,
        max_hours_ago=body.max_hours_ago,
        require_email=body.require_email,
        require_phone=body.require_phone,
        require_name=body.require_name,
    )

    matches: list[ResultOut] = []
    rejected: list[ResultOut] = []
    filtered_out = 0

    limit = min(len(chunks), body.max_results)
    for i in range(limit):
        chunk = chunks[i]
        item_platform = platforms[i] if i < len(platforms) else body.source
        item = storage.save_item(
            db,
            chunk.text,
            source=item_platform,
            url=chunk.url,
        )
        decision = classify_message(profile_data, chunk.text, platform=item_platform)
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

        # Stricter accuracy gate for deep mode
        if body.deep and out.is_match and out.genuine_score < settings.discover_min_genuine:
            out.is_match = False
            out.reason = f"{(out.reason or '').strip()} (below genuineness threshold)".strip()

        if not passes_soft_filters(soft, out):
            filtered_out += 1
            out.is_match = False
            out.reason = f"{(out.reason or '').strip()} (removed by time/contact filters)".strip()
            rejected.append(out)
            continue

        if out.is_match and result.is_match:
            matches.append(out)
        else:
            rejected.append(out)

    match_dicts = [m.model_dump() for m in matches]
    if body.deep and match_dicts:
        match_dicts = rerank_matches_with_ai(profile.intent, match_dicts)
        # Drop weak after rerank
        strong = []
        weak = []
        for m in match_dicts:
            if float(m.get("genuine_score") or 0) >= settings.discover_min_genuine:
                strong.append(ResultOut.model_validate(m))
            else:
                m["is_match"] = False
                m["reason"] = f"{m.get('reason') or ''} (reranked as weak)".strip()
                weak.append(ResultOut.model_validate(m))
        matches = strong
        rejected.extend(weak)
    else:
        matches.sort(key=lambda r: (r.genuine_score, r.confidence), reverse=True)

    return FilterResponse(
        total_items=limit,
        source=body.source,
        matches=matches,
        rejected=rejected,
        filtered_out=filtered_out,
    )
