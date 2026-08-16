from sqlalchemy import Boolean, CheckConstraint, Column, Float, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(collation="NOCASE"))
    hashed_password = Column(String, nullable=True)
    __table_args__ = (
        Index("ix_users_username", username.collate("BINARY"), unique=True),
        Index("uq_users_username_nocase", username, unique=True),
    )
    entries = relationship("Entry", back_populates="owner")
    memberships = relationship("BeerRunMember", back_populates="user")

class BeerRun(Base):
    __tablename__ = "beer_runs"
    __table_args__ = (
        Index("ix_beer_runs_is_public", "is_public"),
        Index("uq_beer_runs_name_nocase", "name", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(collation="NOCASE"), nullable=False, index=True)
    is_public = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    memberships = relationship("BeerRunMember", back_populates="beer_run")
    entries = relationship("Entry", back_populates="beer_run")
    invites = relationship("BeerRunInvite", back_populates="beer_run", uselist=False)

class BeerRunMember(Base):
    __tablename__ = "beer_run_members"
    __table_args__ = (
        UniqueConstraint("beer_run_id", "user_id", name="uq_beer_run_members_run_user"),
        CheckConstraint("role IN ('owner', 'member')", name="ck_beer_run_members_role"),
        Index("ix_beer_run_members_beer_run_id", "beer_run_id"),
        Index("ix_beer_run_members_user_id", "user_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    beer_run_id = Column(Integer, ForeignKey("beer_runs.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    beer_run = relationship("BeerRun", back_populates="memberships")
    user = relationship("User", back_populates="memberships")

class Entry(Base):
    __tablename__ = "entries"

    id = Column(Integer, primary_key=True, index=True)
    drink_type = Column(String)  # e.g., Beer, Sake, Chu-hi
    abv = Column(Float)          # Alcohol percentage
    quantity = Column(Float)     # Volume in Liters
    brand = Column(String, nullable=True)
    latitude = Column(Float)
    longitude = Column(Float)
    image_path = Column(String, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))
    timezone = Column(String, nullable=True)
    timezone_code = Column(String, nullable=True)
    
    user_id = Column(Integer, ForeignKey("users.id"))
    beer_run_id = Column(Integer, ForeignKey("beer_runs.id"), nullable=True)
    owner = relationship("User", back_populates="entries")
    beer_run = relationship("BeerRun", back_populates="entries")

class BeerRunInvite(Base):
    """One permanent reusable invite per beer-run.

    The raw ``code`` is persisted in recoverable form because the owner-only
    create endpoint doubles as retrieval: it must return the same permanent
    link forever. Possession of a code is a bearer capability for preview and
    acceptance, so the code is sensitive data — invite-handling code must never
    log it, include it in error details, or return it outside the owner-only
    create-or-retrieve response.
    """
    __tablename__ = "beer_run_invites"
    __table_args__ = (
        # At most one invite per run.
        UniqueConstraint("beer_run_id", name="uq_beer_run_invites_beer_run_id"),
        # Globally unique, case-sensitive bearer code (default BINARY collation).
        UniqueConstraint("code", name="uq_beer_run_invites_code"),
        # Codes are exactly 43 unpadded URL-safe characters from [A-Za-z0-9_-].
        # The negated GLOB ensures every character is in the allowed set.
        CheckConstraint(
            "length(code) = 43 AND code NOT GLOB '*[^A-Za-z0-9_-]*'",
            name="ck_beer_run_invites_code_format",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    beer_run_id = Column(Integer, ForeignKey("beer_runs.id"), nullable=False)
    code = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    beer_run = relationship("BeerRun", back_populates="invites")
