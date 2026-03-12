from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    entries = relationship("Entry", back_populates="owner")

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
    
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="entries")
