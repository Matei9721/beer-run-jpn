import os
import io
import json
from functools import lru_cache
from datetime import datetime
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any
from PIL import Image, ImageOps

import models
import schemas
import auth
from database import engine, get_db

# Create the database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="BoozeRunJpn")

# Ensure static directories exist
os.makedirs("static/uploads", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@lru_cache()
def get_drink_config() -> Dict[str, Any]:
    try:
        with open("data/drinks.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"types": [], "quantities": []}

def parse_client_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now().astimezone().replace(tzinfo=None)

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.now().astimezone().replace(tzinfo=None)

    return parsed.replace(tzinfo=None)

def save_optimized_image(contents: bytes, image_path: str) -> None:
    img = Image.open(io.BytesIO(contents))
    img = ImageOps.exif_transpose(img)

    # Convert to RGB (in case of RGBA/PNG)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Resize if too large (max 1080px on longest side)
    max_size = 1080
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    # Save as optimized JPEG with the orientation baked into the pixels.
    img.save(image_path, "JPEG", quality=85, optimize=True)

@app.get("/")
async def root():
    return FileResponse("templates/index.html")

@app.get("/api/config")
async def get_config():
    return get_drink_config()

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    print(f"Login attempt for user: {form_data.username}")
    # Case-insensitive search
    user = db.query(models.User).filter(func.lower(models.User.username) == func.lower(form_data.username)).first()
    if not user:
        print(f"User {form_data.username} not found")
    elif not user.hashed_password:
        print(f"User {form_data.username} has no hashed_password")
    elif not auth.verify_password(form_data.password, user.hashed_password):
        print(f"Password mismatch for user: {form_data.username}")
    
    if not user or not user.hashed_password or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/me")
async def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return {"username": current_user.username, "id": current_user.id}

@app.get("/api/leaderboard")
async def get_leaderboard(db: Session = Depends(get_db)):
    # Basic leaderboard logic: sum of quantity and total alcohol consumed
    # (Simplified for now, will expand in Phase 2)
    users = db.query(models.User).all()
    leaderboard = []
    for user in users:
        total_liters = sum(e.quantity for e in user.entries)
        # Total pure alcohol: quantity * (abv/100)
        total_alcohol = sum(e.quantity * (e.abv / 100.0) for e in user.entries)
        leaderboard.append({
            "username": user.username,
            "total_liters": total_liters,
            "total_alcohol": total_alcohol
        })
    # Sort by total liters
    leaderboard.sort(key=lambda x: x["total_alcohol"], reverse=True)
    return leaderboard

@app.get("/api/entries")
async def get_entries(username: str = None, db: Session = Depends(get_db)):
    query = db.query(models.Entry)
    if username:
        query = query.join(models.User).filter(models.User.username == username)
    entries = query.order_by(models.Entry.timestamp.desc()).all()
    
    return [{
        "id": e.id,
        "username": e.owner.username,
        "drink_type": e.drink_type,
        "abv": e.abv,
        "quantity": e.quantity,
        "brand": e.brand,
        "latitude": e.latitude,
        "longitude": e.longitude,
        "image_path": e.image_path,
        "timestamp": e.timestamp.isoformat(),
        "timezone": e.timezone,
        "timezone_code": e.timezone_code
    } for e in entries]

@app.post("/api/entries")
async def create_entry(
    drink_type: str = Form(...),
    abv: float = Form(...),
    quantity: float = Form(...),
    brand: str = Form(None),
    latitude: float = Form(...),
    longitude: float = Form(...),
    client_timestamp: str = Form(None),
    client_timezone: str = Form(None),
    client_timezone_code: str = Form(None),
    image: UploadFile = File(None),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    print(f"Creating entry for {current_user.username}: {drink_type}, {abv}%, {quantity}L")
    image_path = None
    if image and image.filename and image.filename.strip():
        print(f"Processing image: {image.filename}")
        try:
            # Read image data first to check if it has content
            contents = await image.read()
            if not contents:
                print("Image field exists but is empty (0 bytes). Skipping processing.")
            else:
                # Generate filename
                timestamp = int(models.datetime.now(models.UTC).timestamp())
                # Ensure filename is safe or just use a generic name
                safe_filename = f"{timestamp}.jpg"
                image_path = os.path.join("static/uploads", safe_filename)
                
                save_optimized_image(contents, image_path)
                print(f"Image saved to: {image_path}")
        except Exception as e:
            print(f"Image processing failed: {e}")
            raise HTTPException(status_code=500, detail=f"Image processing error: {str(e)}")

    try:
        new_entry = models.Entry(
            drink_type=drink_type,
            abv=abv,
            quantity=quantity,
            brand=brand,
            latitude=latitude,
            longitude=longitude,
            image_path=image_path,
            timestamp=parse_client_timestamp(client_timestamp),
            timezone=client_timezone,
            timezone_code=client_timezone_code,
            user_id=current_user.id
        )
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        print(f"Entry created with ID: {new_entry.id}")
        return {"status": "success", "entry_id": new_entry.id}
    except Exception as e:
        print(f"Database error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
