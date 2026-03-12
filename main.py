import os
import io
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
from PIL import Image

import models
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

@app.get("/")
async def root():
    return FileResponse("templates/index.html")

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
    leaderboard.sort(key=lambda x: x["total_liters"], reverse=True)
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
        "timestamp": e.timestamp.isoformat()
    } for e in entries]

@app.post("/api/entries")
async def create_entry(
    username: str = Form(...),
    drink_type: str = Form(...),
    abv: float = Form(...),
    quantity: float = Form(...),
    brand: str = Form(None),
    latitude: float = Form(...),
    longitude: float = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # Ensure user exists or create them
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        user = models.User(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)

    image_path = None
    if image:
        # Generate filename
        timestamp = int(models.datetime.now(models.UTC).timestamp())
        filename = f"{timestamp}_{image.filename.split('.')[0]}.jpg"
        image_path = os.path.join("static/uploads", filename)
        
        # Read image data
        contents = await image.read()
        img = Image.open(io.BytesIO(contents))
        
        # Convert to RGB (in case of RGBA/PNG)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # Resize if too large (max 1080px on longest side)
        max_size = 1080
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
        # Save as optimized JPEG
        img.save(image_path, "JPEG", quality=85, optimize=True)

    new_entry = models.Entry(
        drink_type=drink_type,
        abv=abv,
        quantity=quantity,
        brand=brand,
        latitude=latitude,
        longitude=longitude,
        image_path=image_path,
        user_id=user.id
    )
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    
    return {"status": "success", "entry_id": new_entry.id}
