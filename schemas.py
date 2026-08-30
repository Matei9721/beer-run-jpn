from pydantic import BaseModel, ConfigDict, StrictStr
from datetime import datetime
from typing import Optional

class EntryBase(BaseModel):
    drink_type: str
    abv: float
    quantity: float
    brand: Optional[str] = None
    latitude: float
    longitude: float

class Entry(EntryBase):
    id: int
    username: str
    image_path: Optional[str] = None
    timestamp: datetime
    timezone: Optional[str] = None
    timezone_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class LeaderboardUser(BaseModel):
    username: str
    total_liters: float
    total_alcohol: float

class Token(BaseModel):
    access_token: str
    token_type: str


class SignupRequest(BaseModel):
    username: StrictStr
    password: StrictStr
    signup_code: StrictStr


class AccountDeleteRequest(BaseModel):
    password: StrictStr
    confirmation: StrictStr


class OwnedRunSummary(BaseModel):
    id: int
    name: str


class AccountDeletionSummary(BaseModel):
    entry_count: int
    membership_count: int
    owned_runs: list[OwnedRunSummary]


class AccountDeleteResponse(BaseModel):
    deleted: bool


# --- Beer-Run Schemas ---

class BeerRunCreateRequest(BaseModel):
    """JSON body for POST /api/beer-runs."""
    name: str
    is_public: bool = False


class BeerRunUpdateRequest(BaseModel):
    """JSON body for PATCH /api/beer-runs/{beer_run_id}.

    At least one field must be present — the route enforces this, not Pydantic,
    because Pydantic's model-level validation makes it harder to return a
    clean 422 that matches the project's error style.
    """
    name: Optional[str] = None
    is_public: Optional[bool] = None


class BeerRunResponse(BaseModel):
    """Single beer-run shape returned by create, list, detail, and update."""
    id: int
    name: str
    is_public: bool
    created_at: datetime
    member_count: int
    current_user_role: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BeerRunDeleteResponse(BaseModel):
    """Stable response returned after a beer-run has been deleted."""

    status: str
    beer_run_id: int


class BeerRunMemberResponse(BaseModel):
    """A member visible to anyone authorized to read the beer-run."""

    user_id: int
    username: str
    role: str

    model_config = ConfigDict(from_attributes=True)


# --- Invite Schemas ---

class InviteCreateResponse(BaseModel):
    """Owner-only create-or-retrieve response for a run's permanent invite.

    ``invite_url`` is an origin-independent root-relative URL in the form
    ``/?invite=<code>``. The raw ``code`` is sensitive and appears only in this
    owner-only response — never in preview, acceptance, logs, or errors.
    """
    code: str
    invite_url: str
    beer_run_id: int
    beer_run_name: str
    created_at: datetime


class InvitePreviewResponse(BaseModel):
    """Public minimal preview for a valid invite code.

    Deliberately limited to run identity — no visibility, owner, membership,
    entry, or other run data (FR-2.4).
    """
    beer_run_id: int
    beer_run_name: str
