import json
import sqlite3
from pathlib import Path

from scripts.build_wrapped_data import build_wrapped_data


def test_wrapped_page_and_api(client):
    page_response = client.get("/wrapped")
    assert page_response.status_code == 200
    assert "text/html" in page_response.headers["content-type"]
    assert "BeerRunJPN Wrapped" in page_response.text

    api_response = client.get("/api/wrapped")
    assert api_response.status_code == 200
    data = api_response.json()
    assert data["meta"]["title"] == "BeerRunJPN Wrapped"
    assert len(data["slides"]) >= 1


def test_build_wrapped_data_skips_empty_images(tmp_path):
    db_path = tmp_path / "trip.db"
    root = tmp_path
    uploads = root / "static" / "uploads"
    uploads.mkdir(parents=True)
    (uploads / "valid.jpg").write_bytes(b"not-empty")
    (uploads / "valid2.jpg").write_bytes(b"also-not-empty")
    (uploads / "empty.jpg").write_bytes(b"")

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        create table users (
            id integer primary key,
            username text
        );

        create table entries (
            id integer primary key,
            drink_type text,
            brand text,
            quantity real,
            abv real,
            latitude real,
            longitude real,
            image_path text,
            timestamp text,
            user_id integer
        );
        """
    )
    conn.execute("insert into users (id, username) values (1, 'Tester')")
    conn.execute(
        """
        insert into entries
            (id, drink_type, brand, quantity, abv, latitude, longitude, image_path, timestamp, user_id)
        values
            (1, 'Beer', 'Proof', 0.5, 5.0, 35.7, 139.7, 'static/uploads/valid.jpg', '2026-03-24 10:00:00', 1),
            (2, 'Whiskey', 'Broken', 0.05, 55.0, 35.7, 139.7, 'static/uploads/empty.jpg', '2026-03-24 11:00:00', 1),
            (3, 'Highball', 'Proof 2', 0.35, 7.0, 35.96, 139.59, 'static/uploads/valid2.jpg', '2026-03-25 11:00:00', 1)
        """
    )
    conn.commit()
    conn.close()

    output_path = tmp_path / "wrapped.json"
    data = build_wrapped_data(db_path=db_path, output_path=output_path, root=root)
    rendered = json.dumps(data)

    assert output_path.exists()
    assert data["stats"]["total_entries"] == 3
    assert data["stats"]["total_photos"] == 2
    assert "/static/uploads/valid.jpg" in rendered
    assert "/static/uploads/valid2.jpg" in rendered
    assert "/static/uploads/empty.jpg" not in rendered

    layouts = {slide["layout"] for slide in data["slides"]}
    assert {"date-range", "timeline", "calendar", "multi-image"}.issubset(layouts)

    timeline = next(slide for slide in data["slides"] if slide["layout"] == "timeline")
    assert len(timeline["timeline"]["checkpoints"]) >= 2
    assert timeline["timeline"]["series"]

    calendar = next(slide for slide in data["slides"] if slide["layout"] == "calendar")
    calendar_days = [day for week in calendar["calendar"]["weeks"] for day in week]
    assert calendar["calendar"]["active_days"] == 2
    assert calendar_days[-1]["date"] == "2026-03-25"
    assert any(day["entries"] == 2 and day["liters"] == 0.55 for day in calendar_days)
    assert any(day["entries"] == 1 and day["liters"] == 0.35 for day in calendar_days)

    multi_image = next(slide for slide in data["slides"] if slide["layout"] == "multi-image")
    assert multi_image["images"]

    locations = next(slide for slide in data["slides"] if slide["layout"] == "locations")
    assert all(location["name"] != "Japan" for location in locations["locations"])
