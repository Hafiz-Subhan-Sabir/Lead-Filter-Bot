"""
PythonAnywhere-friendly Flask app (plain WSGI — no a2wsgi / ASGI).

Point PA WSGI file at:
  from pa_app import application
"""
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from database import SessionLocal, init_db  # noqa: E402
from routers.filter import decision_to_result, passes_soft_filters  # noqa: E402
from schemas import FilterRequest, ProfileCreate  # noqa: E402
from services import storage  # noqa: E402
from services.ai_filter import classify_message  # noqa: E402
from services.splitter import split_into_items  # noqa: E402

FRONTEND_DIR = PROJECT_ROOT / "frontend"

init_db()

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="/static")


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
        matches = []
        rejected = []
        filtered_out = 0

        for chunk in chunks:
            item = storage.save_item(
                db,
                chunk.text,
                source=body.source,
                url=chunk.url,
            )
            decision = classify_message(
                profile_data,
                chunk.text,
                platform=body.source,
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
                continue

            payload = out.model_dump()
            if result.is_match:
                matches.append(payload)
            else:
                rejected.append(payload)

        return jsonify(
            {
                "total_items": len(chunks),
                "source": body.source,
                "matches": matches,
                "rejected": rejected,
                "filtered_out": filtered_out,
            }
        )
    finally:
        db.close()


application = app
