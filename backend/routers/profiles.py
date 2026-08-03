from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas import ProfileCreate, ProfileOut
from services import storage

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("", response_model=ProfileOut)
def create_profile(body: ProfileCreate, db: Session = Depends(get_db)):
    return storage.create_profile(db, body)


@router.get("/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    profile = storage.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile
