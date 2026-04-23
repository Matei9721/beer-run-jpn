from pydantic import BaseModel, ConfigDict
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
