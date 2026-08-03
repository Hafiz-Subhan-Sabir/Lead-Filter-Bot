from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class FilterProfile(Base):
    __tablename__ = "filter_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    intent: Mapped[str] = mapped_column(Text)
    want_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    want_onsite: Mapped[bool] = mapped_column(Boolean, default=False)
    want_hiring: Mapped[bool] = mapped_column(Boolean, default=True)
    want_startups: Mapped[bool] = mapped_column(Boolean, default=False)
    want_no_website: Mapped[bool] = mapped_column(Boolean, default=False)
    min_confidence: Mapped[float] = mapped_column(Float, default=0.7)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    results: Mapped[list["FilterResult"]] = relationship(back_populates="profile")


class RawItem(Base):
    __tablename__ = "raw_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), default="paste")
    source_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    results: Mapped[list["FilterResult"]] = relationship(back_populates="item")


class FilterResult(Base):
    __tablename__ = "filter_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("raw_items.id"))
    profile_id: Mapped[int] = mapped_column(ForeignKey("filter_profiles.id"))

    is_match: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    work_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    company_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False)
    has_website: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    item: Mapped["RawItem"] = relationship(back_populates="results")
    profile: Mapped["FilterProfile"] = relationship(back_populates="results")
