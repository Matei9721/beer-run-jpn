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
