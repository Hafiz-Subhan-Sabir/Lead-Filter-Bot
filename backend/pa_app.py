"""
PythonAnywhere-friendly Flask app (plain WSGI).
"""
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from config import settings  # noqa: E402
from database import SessionLocal, init_db  # noqa: E402
from routers.discover import DiscoverRequest  # noqa: E402
from routers.filter import decision_to_result, passes_soft_filters  # noqa: E402
from schemas import FilterRequest, ProfileCreate  # noqa: E402
from services import storage  # noqa: E402
from services.ai_filter import classify_message  # noqa: E402
from services.discover import discover_items, rerank_matches_with_ai  # noqa: E402
from services.platform_detect import resolve_item_platform  # noqa: E402
from services.splitter import ParsedItem, split_into_items  # noqa: E402

FRONTEND_DIR = PROJECT_ROOT / "frontend"

init_db()

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="/static")


@app.errorhandler(Exception)
def handle_unexpected(err):
    return jsonify({"detail": f"{type(err).__name__}: {err}"}), 500


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.post("/profiles")
def create_profile():
    try:
        body = ProfileCreate.model_validate(request.get_json(force=True))
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    db = SessionLocal()
    try:
        profile = storage.create_profile(db, body)
        return jsonify(
            {
                "id": profile.id,
                "name": profile.name,
                "intent": profile.intent,
                "want_remote": profile.want_remote,
                "want_onsite": profile.want_onsite,
                "want_hiring": profile.want_hiring,
                "want_startups": profile.want_startups,
                "want_no_website": profile.want_no_website,
                "min_confidence": profile.min_confidence,
            }
        )
    finally:
        db.close()


@app.get("/profiles/<int:profile_id>")
def get_profile(profile_id: int):
    db = SessionLocal()
    try:
        profile = storage.get_profile(db, profile_id)
        if not profile:
            return jsonify({"detail": "Profile not found"}), 404
        return jsonify(
            {
                "id": profile.id,
                "name": profile.name,
                "intent": profile.intent,
                "want_remote": profile.want_remote,
                "want_onsite": profile.want_onsite,
                "want_hiring": profile.want_hiring,
                "want_startups": profile.want_startups,
                "want_no_website": profile.want_no_website,
                "min_confidence": profile.min_confidence,
            }
        )
    finally:
        db.close()


@app.post("/filter/run")
def run_filter():
    try:
        body = FilterRequest.model_validate(request.get_json(force=True))
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    db = SessionLocal()
    try:
        profile = storage.get_profile(db, body.profile_id)
        if not profile:
            return jsonify({"detail": "Profile not found"}), 404

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
        if not chunks:
            return jsonify({"detail": "No valid posts found in paste text"}), 400

        matches = []
        rejected = []
        filtered_out = 0

        for chunk in chunks:
            item_platform = resolve_item_platform(body.source, chunk.url)
            item = storage.save_item(
                db,
                chunk.text,
                source=item_platform,
                url=chunk.url,
            )
            decision = classify_message(
                profile_data,
                chunk.text,
                platform=item_platform,
            )
            if (
                chunk.hours_ago_hint is not None
                and decision.extracted.hours_ago_estimate is None
            ):
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
                out.is_match = False
                out.reason = f"{(out.reason or '').strip()} (removed by time/contact filters)".strip()
                rejected.append(out.model_dump())
                continue

            payload = out.model_dump()
            if result.is_match:
                matches.append(payload)
            else:
                rejected.append(payload)

        matches.sort(
            key=lambda r: (r.get("genuine_score", 0), r.get("confidence", 0)),
            reverse=True,
        )

        return jsonify(
            {
                "total_items": len(chunks),
                "source": body.source,
                "matches": matches,
                "rejected": rejected,
                "filtered_out": filtered_out,
            }
        )
    except Exception as exc:
        return jsonify({"detail": f"{type(exc).__name__}: {exc}"}), 500
    finally:
        db.close()


@app.post("/discover/run")
def run_discover():
    try:
        body = DiscoverRequest.model_validate(request.get_json(force=True))
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    db = SessionLocal()
    try:
        profile = storage.get_profile(db, body.profile_id)
        if not profile:
            return jsonify({"detail": "Profile not found"}), 404

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
            return jsonify(
                {
                    "detail": (
                        "No public posts found for this intent/platform. "
                        "Try a clearer intent or add BRAVE_API_KEY / SERPAPI_KEY in .env."
                    )
                }
            ), 404

        soft = FilterRequest(
            text="x",
            profile_id=body.profile_id,
            source=body.source,
            max_hours_ago=body.max_hours_ago,
            require_email=body.require_email,
            require_phone=body.require_phone,
            require_name=body.require_name,
        )

        matches = []
        rejected = []
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
            decision = classify_message(
                profile_data,
                chunk.text,
                platform=item_platform,
            )
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

            if body.deep and out.is_match and out.genuine_score < settings.discover_min_genuine:
                out.is_match = False
                out.reason = f"{(out.reason or '').strip()} (below genuineness threshold)".strip()

            if not passes_soft_filters(soft, out):
                filtered_out += 1
                out.is_match = False
                out.reason = f"{(out.reason or '').strip()} (removed by time/contact filters)".strip()
                rejected.append(out.model_dump())
                continue

            payload = out.model_dump()
            if out.is_match and result.is_match:
                matches.append(payload)
            else:
                rejected.append(payload)

        if body.deep and matches:
            matches = rerank_matches_with_ai(profile.intent, matches)
            strong = []
            for m in matches:
                if float(m.get("genuine_score") or 0) >= settings.discover_min_genuine:
                    strong.append(m)
                else:
                    m["is_match"] = False
                    m["reason"] = f"{m.get('reason') or ''} (reranked as weak)".strip()
                    rejected.append(m)
            matches = strong
        else:
            matches.sort(
                key=lambda r: (r.get("genuine_score", 0), r.get("confidence", 0)),
                reverse=True,
            )

        return jsonify(
            {
                "total_items": limit,
                "source": body.source,
                "matches": matches,
                "rejected": rejected,
                "filtered_out": filtered_out,
            }
        )
    except Exception as exc:
        return jsonify({"detail": f"{type(exc).__name__}: {exc}"}), 500
    finally:
        db.close()


application = app
