import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, UTC
from pathlib import Path


DEFAULT_DB_PATH = Path("boozerun.db")
DEFAULT_OUTPUT_PATH = Path("data/wrapped.json")
DEFAULT_ROOT = Path(".")
DEFAULT_AUDIO_PATH = "/static/audio/wrapped.mp3"


def normalize_static_path(path_value):
    if not path_value:
        return None

    normalized = str(path_value).replace("\\", "/").lstrip("/")
    return normalized or None


def public_static_path(path_value):
    normalized = normalize_static_path(path_value)
    return f"/{normalized}" if normalized else None


def parse_timestamp(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def format_trip_date(value):
    parsed = parse_timestamp(value)
    if not parsed:
        return ""
    return parsed.strftime("%b %-d, %Y") if hasattr(parsed, "strftime") else str(value)


def format_trip_date_portable(value):
    parsed = parse_timestamp(value)
    if not parsed:
        return ""
    return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}"


def format_trip_short(value):
    parsed = parse_timestamp(value)
    if not parsed:
        return ""
    return f"{parsed.strftime('%b')} {parsed.day}"


def image_exists(root, image_path):
    normalized = normalize_static_path(image_path)
    if not normalized:
        return False
    candidate = root / normalized
    return candidate.is_file() and candidate.stat().st_size > 0


def load_entries(db_path, root):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            select entries.id,
                   users.username,
                   drink_type,
                   brand,
                   quantity,
                   abv,
                   latitude,
                   longitude,
                   image_path,
                   timestamp
            from entries
            join users on users.id = entries.user_id
            order by timestamp asc, entries.id asc
            """
        ).fetchall()
    finally:
        conn.close()

    entries = []
    for row in rows:
        item = dict(row)
        item["quantity"] = float(item["quantity"] or 0)
        item["abv"] = float(item["abv"] or 0)
        item["pure_alcohol"] = item["quantity"] * item["abv"] / 100
        item["image_path"] = normalize_static_path(item.get("image_path"))
        item["image_url"] = public_static_path(item.get("image_path")) if image_exists(root, item.get("image_path")) else None
        item["timestamp_sort"] = parse_timestamp(item.get("timestamp")) or datetime.min
        entries.append(item)

    return entries


def entry_label(entry):
    if not entry:
        return ""
    brand = entry.get("brand")
    drink = entry.get("drink_type") or "Drink"
    return f"{drink} - {brand}" if brand else drink


def find_entry(entries, preferred_ids=None, predicate=None, sort_key=None, reverse=True):
    preferred_ids = preferred_ids or []
    by_id = {int(entry["id"]): entry for entry in entries}
    for preferred_id in preferred_ids:
        entry = by_id.get(int(preferred_id))
        if entry and entry.get("image_url") and (predicate is None or predicate(entry)):
            return entry

    candidates = [entry for entry in entries if entry.get("image_url") and (predicate is None or predicate(entry))]
    if not candidates:
        return None

    if sort_key:
        candidates.sort(key=sort_key, reverse=reverse)
    return candidates[0]


def classify_location(lat, lon):
    if lat is None or lon is None:
        return "Unplaced"
    if lat > 42:
        return "Sapporo"
    if 36 <= lat <= 37 and 138 <= lon <= 139:
        return "Kusatsu"
    if 34.5 <= lat <= 35.2 and 135 <= lon <= 136:
        return "Kansai"
    if 35.45 <= lat <= 35.85 and 139.4 <= lon <= 140:
        return "Tokyo"
    if 35.85 <= lat <= 36.15 and 139.2 <= lon <= 139.9:
        return "Saitama"
    if 35.25 <= lat <= 35.75 and 138.45 <= lon <= 139.15:
        return "Fuji area"
    return "Other stops"


def build_location_stats(entries):
    grouped = defaultdict(lambda: {"entries": 0, "pure_alcohol": 0.0})
    for entry in entries:
        label = classify_location(entry.get("latitude"), entry.get("longitude"))
        grouped[label]["entries"] += 1
        grouped[label]["pure_alcohol"] += entry["pure_alcohol"]

    locations = [
        {
            "name": name,
            "entries": data["entries"],
            "pure_alcohol": round(data["pure_alcohol"], 3),
        }
        for name, data in grouped.items()
    ]
    locations.sort(key=lambda item: (item["entries"], item["pure_alcohol"]), reverse=True)
    return locations


def build_leaderboard(entries):
    grouped = defaultdict(lambda: {"entries": 0, "liters": 0.0, "pure_alcohol": 0.0})
    for entry in entries:
        user = entry["username"]
        grouped[user]["entries"] += 1
        grouped[user]["liters"] += entry["quantity"]
        grouped[user]["pure_alcohol"] += entry["pure_alcohol"]

    leaderboard = [
        {
            "username": username,
            "entries": data["entries"],
            "liters": round(data["liters"], 2),
            "pure_alcohol": round(data["pure_alcohol"], 3),
        }
        for username, data in grouped.items()
    ]
    leaderboard.sort(key=lambda item: item["pure_alcohol"], reverse=True)
    return leaderboard


def build_timeline(entries):
    users = sorted({entry["username"] for entry in entries})
    totals = {user: 0.0 for user in users}
    checkpoints = []
    current_date = None

    for entry in entries:
        parsed = entry.get("timestamp_sort")
        date_key = parsed.date().isoformat() if parsed and parsed != datetime.min else "Unknown"
        if current_date and date_key != current_date:
            checkpoints.append({"date": current_date, "totals": {user: round(totals[user], 3) for user in users}})
        current_date = date_key
        totals[entry["username"]] += entry["pure_alcohol"]

    if current_date:
        checkpoints.append({"date": current_date, "totals": {user: round(totals[user], 3) for user in users}})

    if len(checkpoints) <= 9:
        sampled = checkpoints
    else:
        indexes = {0, len(checkpoints) - 1}
        for offset in range(1, 8):
            indexes.add(round(offset * (len(checkpoints) - 1) / 8))
        sampled = [checkpoint for index, checkpoint in enumerate(checkpoints) if index in indexes]

    for checkpoint in sampled:
        checkpoint["label"] = format_trip_short(checkpoint["date"])

    return {
        "unit": "L pure alcohol",
        "series": [
            {"username": user, "values": [checkpoint["totals"].get(user, 0) for checkpoint in sampled]}
            for user in users
        ],
        "checkpoints": [{"date": item["date"], "label": item["label"]} for item in sampled],
    }


def format_calendar_month_range(start_day, end_day):
    if start_day.year == end_day.year and start_day.month == end_day.month:
        return f"{start_day.strftime('%b')} {start_day.year}"
    if start_day.year == end_day.year:
        return f"{start_day.strftime('%b')} - {end_day.strftime('%b')} {end_day.year}"
    return f"{start_day.strftime('%b')} {start_day.year} - {end_day.strftime('%b')} {end_day.year}"


def format_calendar_day(day):
    return f"{day.strftime('%b')} {day.day}"


def build_calendar(entries):
    dated_entries = [
        entry
        for entry in entries
        if entry.get("timestamp_sort") and entry["timestamp_sort"] != datetime.min
    ]
    if not dated_entries:
        return {
            "month_label": "",
            "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "weeks": [],
            "active_days": 0,
            "total_days": 0,
            "max_entries": 0,
            "max_liters": 0,
            "highlights": [],
        }

    grouped = defaultdict(lambda: {"entries": 0, "liters": 0.0, "pure_alcohol": 0.0})
    for entry in dated_entries:
        day = entry["timestamp_sort"].date()
        grouped[day]["entries"] += 1
        grouped[day]["liters"] += entry["quantity"]
        grouped[day]["pure_alcohol"] += entry["pure_alcohol"]

    start_day = min(grouped)
    end_day = max(grouped)
    calendar_start = start_day - timedelta(days=start_day.weekday())
    calendar_end = end_day
    max_entries = max(day["entries"] for day in grouped.values())
    max_liters = max(day["liters"] for day in grouped.values())
    busiest_day, busiest_data = max(grouped.items(), key=lambda item: (item[1]["entries"], item[1]["liters"]))
    thirstiest_day, thirstiest_data = max(grouped.items(), key=lambda item: (item[1]["liters"], item[1]["entries"]))

    weeks = []
    cursor = calendar_start
    while cursor <= calendar_end:
        week = []
        for _ in range(7):
            if cursor > calendar_end:
                break
            in_range = start_day <= cursor <= end_day
            day_data = grouped.get(cursor, {"entries": 0, "liters": 0.0, "pure_alcohol": 0.0})
            entries_count = day_data["entries"] if in_range else 0
            liters = day_data["liters"] if in_range else 0.0
            intensity = 0
            if in_range and entries_count:
                entry_intensity = entries_count / max(max_entries, 1)
                liter_intensity = liters / max(max_liters, 0.001)
                intensity = round(max(entry_intensity, liter_intensity), 3)
            week.append(
                {
                    "date": cursor.isoformat(),
                    "day": cursor.day,
                    "month": cursor.strftime("%b"),
                    "label": format_calendar_day(cursor),
                    "weekday": cursor.strftime("%a"),
                    "entries": entries_count,
                    "liters": round(liters, 2),
                    "pure_alcohol": round(day_data["pure_alcohol"] if in_range else 0, 3),
                    "intensity": intensity,
                    "in_range": in_range,
                    "is_peak_entries": in_range and cursor == busiest_day,
                    "is_peak_liters": in_range and cursor == thirstiest_day,
                }
            )
            cursor += timedelta(days=1)
        weeks.append(week)

    total_days = (end_day - start_day).days + 1
    active_days = sum(1 for data in grouped.values() if data["entries"] > 0)
    return {
        "month_label": format_calendar_month_range(start_day, end_day),
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "weeks": weeks,
        "active_days": active_days,
        "total_days": total_days,
        "max_entries": max_entries,
        "max_liters": round(max_liters, 2),
        "highlights": [
            {
                "label": "most drinks",
                "date": format_calendar_day(busiest_day),
                "value": f"{busiest_data['entries']} drinks",
            },
            {
                "label": "most volume",
                "date": format_calendar_day(thirstiest_day),
                "value": f"{thirstiest_data['liters']:.2f}L",
            },
        ],
    }


def sample_photo_wall(entries, limit=12):
    images = [entry for entry in entries if entry.get("image_url")]
    if len(images) <= limit:
        return [
            {"src": entry["image_url"], "alt": entry_label(entry)}
            for entry in images
        ]

    selected = []
    step = (len(images) - 1) / (limit - 1)
    seen = set()
    for index in range(limit):
        entry = images[round(index * step)]
        if entry["image_url"] in seen:
            continue
        selected.append({"src": entry["image_url"], "alt": entry_label(entry)})
        seen.add(entry["image_url"])
    return selected


def as_image(entry, fallback_alt):
    if not entry or not entry.get("image_url"):
        return None
    return {
        "src": entry["image_url"],
        "alt": entry_label(entry) or fallback_alt,
        "caption": f"{entry.get('username', 'Someone')} - {entry_label(entry)}",
    }


def as_gallery_image(entry):
    if not entry or not entry.get("image_url"):
        return None
    return {"src": entry["image_url"], "alt": entry_label(entry)}


def images_from_ids(entries, preferred_ids, limit):
    by_id = {int(entry["id"]): entry for entry in entries}
    images = []
    seen = set()
    for entry_id in preferred_ids:
        image = as_gallery_image(by_id.get(entry_id))
        if image and image["src"] not in seen:
            images.append(image)
            seen.add(image["src"])
        if len(images) >= limit:
            break
    return images


def build_wrapped_data(db_path=DEFAULT_DB_PATH, output_path=DEFAULT_OUTPUT_PATH, root=DEFAULT_ROOT):
    root = Path(root)
    entries = load_entries(Path(db_path), root)
    valid_photo_count = sum(1 for entry in entries if entry.get("image_url"))
    leaderboard = build_leaderboard(entries)
    locations = build_location_stats(entries)
    timeline = build_timeline(entries)
    calendar = build_calendar(entries)

    drink_counter = Counter(entry["drink_type"] or "Unknown" for entry in entries)
    top_drink, top_drink_count = drink_counter.most_common(1)[0] if drink_counter else ("Nothing", 0)

    date_values = [entry["timestamp_sort"] for entry in entries if entry["timestamp_sort"] != datetime.min]
    start_date = min(date_values).isoformat() if date_values else ""
    end_date = max(date_values).isoformat() if date_values else ""

    total_liters = sum(entry["quantity"] for entry in entries)
    total_alcohol = sum(entry["pure_alcohol"] for entry in entries)

    strongest = find_entry(entries, preferred_ids=[50, 51], sort_key=lambda entry: (entry["abv"], entry["quantity"]))
    intro = find_entry(entries, preferred_ids=[12, 1])
    trip_span_image = find_entry(entries, preferred_ids=[133, 57, 55])
    race_image = find_entry(entries, preferred_ids=[148, 150, 157])
    leaderboard_image = find_entry(entries, preferred_ids=[159, 127, 14])
    drink_of_trip = find_entry(entries, predicate=lambda entry: (entry["drink_type"] or "").lower() == top_drink.lower(), preferred_ids=[162, 12, 173])
    scenic = find_entry(entries, preferred_ids=[56, 55, 145])
    elegant = find_entry(entries, preferred_ids=[113, 121, 50])
    locations_image = find_entry(entries, preferred_ids=[163, 57, 65])
    finale = find_entry(entries, preferred_ids=[173, 170, 169], sort_key=lambda entry: entry["timestamp_sort"])
    plot_twist = find_entry(entries, preferred_ids=[12, 56, 50])

    curated_gallery_ids = [2, 32, 33, 55, 65, 85, 95, 121, 127, 145, 154, 161]
    by_id = {int(entry["id"]): entry for entry in entries}
    curated_gallery = []
    used_gallery_urls = set()
    for entry_id in curated_gallery_ids:
        entry = by_id.get(entry_id)
        if entry and entry.get("image_url") and entry["image_url"] not in used_gallery_urls:
            curated_gallery.append({"src": entry["image_url"], "alt": entry_label(entry)})
            used_gallery_urls.add(entry["image_url"])
    if len(curated_gallery) < 12:
        for image in sample_photo_wall(entries, limit=12):
            if image["src"] not in used_gallery_urls:
                curated_gallery.append(image)
                used_gallery_urls.add(image["src"])
            if len(curated_gallery) >= 12:
                break
    gallery_source_overrides = {
        "Strong Zero - Kirin": "/static/uploads/1776096694.jpg",
        "Beer - Nikka": "/static/uploads/1774952384.jpg",
    }
    for image in curated_gallery:
        override_src = gallery_source_overrides.get(image["alt"])
        if override_src and image_exists(root, override_src):
            image["src"] = override_src
    used_gallery_urls = {image["src"] for image in curated_gallery}

    extra_gallery_images = [
        {"src": "/static/uploads/1775209046.jpg", "alt": "Plum wine soda"},
        {"src": "/static/uploads/1775658438.jpg", "alt": "Chinese strong zero calin"},
        {"src": "/static/uploads/1776431530.jpg", "alt": "Me hiding behind you"},
        {"src": "/static/uploads/1776436405.jpg", "alt": "Miulca"},
        {"src": "/static/uploads/1776589969.jpg", "alt": "Cheers"},
        {"src": "/static/uploads/1776787688.jpg", "alt": "Flamandul"},
        {"src": "/static/uploads/1776436614.jpg", "alt": "Side eye"},
        {"src": "/static/uploads/1776002775.jpg", "alt": "The Choya"},
        {"src": "/static/uploads/1776347702.jpg", "alt": "Lucas"},
        {"src": "/static/uploads/1774423548.jpg", "alt": "sushi"},
        {"src": "/static/uploads/1774794474.jpg", "alt": "Noooo"},
        {"src": "/static/uploads/1774859713.jpg", "alt": "Good food good drinks"},
    ]
    for image in extra_gallery_images:
        if image["src"] not in used_gallery_urls and image_exists(root, image["src"]):
            curated_gallery.append(image)
            used_gallery_urls.add(image["src"])

    group_images = images_from_ids(entries, [14, 15, 127, 159, 2, 95], 4)
    if len(group_images) < 2:
        group_images = curated_gallery[:4]

    lead_gap = 0
    if len(leaderboard) >= 2:
        lead_gap = round(leaderboard[0]["pure_alcohol"] - leaderboard[1]["pure_alcohol"], 3)

    date_range = {
        "start": format_trip_date_portable(start_date),
        "end": format_trip_date_portable(end_date),
        "start_short": format_trip_short(start_date),
        "end_short": format_trip_short(end_date),
    }

    slides = [
        {
            "id": "intro",
            "layout": "intro",
            "kicker": "BeerRunJPN presents",
            "title": "Wrapped",
            "body": "One month in Japan, logged one drink at a time.",
            "image": as_image(intro, "Strong Zero portrait"),
            "stats": [
                {"label": "entries", "value": len(entries)},
                {"label": "photos", "value": valid_photo_count},
            ],
        },
        {
            "id": "trip-span",
            "layout": "date-range",
            "kicker": "Trip window",
            "title": "30 days on record",
            "body": "The log starts in late March and ends at the airport. Sensible boundaries, somehow.",
            "image": as_image(trip_span_image, "Scenic trip drink"),
            "date_range": date_range,
            "stats": [
                {"label": "liters logged", "value": round(total_liters, 2)},
                {"label": "pure alcohol L", "value": round(total_alcohol, 3)},
            ],
        },
        {
            "id": "daily-calendar",
            "layout": "calendar",
            "kicker": "Daily damage report",
            "title": "The calendar did not get many nights off",
            "body": "Each square is one day: drinks logged up top, liters underneath, brighter when the table got busy.",
            "badge": f"{calendar['active_days']} active days of {calendar['total_days']}",
            "calendar": calendar,
            "stats": [
                {"label": "most drinks", "value": calendar["highlights"][0]["value"] if calendar["highlights"] else "0 drinks"},
                {"label": "biggest day", "value": calendar["highlights"][1]["value"] if len(calendar["highlights"]) > 1 else "0L"},
            ],
        },
        {
            "id": "leaderboard-setup",
            "layout": "stat",
            "kicker": "The race",
            "title": "It stayed annoyingly close",
            "body": "Three people, one shared spreadsheet energy, and no comfortable lead.",
            "image": as_image(race_image, "Table race"),
            "stats": [
                {"label": "logged entries", "value": len(entries)},
                {"label": "final lead", "value": f"{lead_gap:.3f}L"},
            ],
        },
        {
            "id": "leaderboard-timeline",
            "layout": "timeline",
            "kicker": "Leaderboard over time",
            "title": "The lead moved late",
            "body": "Jorkormorkor led the early record. Tamei took the official line near the end.",
            "timeline": timeline,
        },
        {
            "id": "logged-ranking",
            "layout": "leaderboard",
            "kicker": "Official logged result",
            "title": "Tamei by a sip",
            "body": f"The recorded lead was {lead_gap:.3f}L of pure alcohol. Close enough to inspect the formulas.",
            "image": as_image(leaderboard_image, "Final standings toast"),
            "leaderboard": leaderboard,
        },
        {
            "id": "plot-twist",
            "layout": "hero",
            "kicker": "Plot twist",
            "title": "The unofficial winner: Jorkormorkor",
            "body": "The database says third. Eyewitnesses remember a few drinks that never made it into the app.",
            "badge": "Claim only. No correction math.",
            "image": as_image(plot_twist, "Unofficial winner"),
        },
        {
            "id": "drink-of-trip",
            "layout": "hero",
            "kicker": "Drink of the trip",
            "title": f"{top_drink} kept showing up",
            "body": f"{top_drink_count} logged appearances. Reliable, available, and rarely subtle.",
            "image": as_image(drink_of_trip, top_drink),
            "stats": [
                {"label": "appearances", "value": top_drink_count},
            ],
        },
        {
            "id": "strongest-pour",
            "layout": "hero",
            "kicker": "Strongest pour",
            "title": f"{entry_label(strongest)}",
            "body": f"{strongest['abv']:.0f}% ABV. Small glass, clear message.",
            "image": as_image(strongest, "Strongest drink"),
            "stats": [
                {"label": "ABV", "value": f"{strongest['abv']:.0f}%"},
                {"label": "logged by", "value": strongest["username"]},
            ],
        },
        {
            "id": "elegant-drink",
            "layout": "hero",
            "kicker": "Most elegant drink",
            "title": "A brief appearance of polish",
            "body": "Stemware helped. So did the lighting.",
            "image": as_image(elegant, "Elegant drink"),
        },
        {
            "id": "scenic-drink",
            "layout": "hero",
            "kicker": "Most scenic drink",
            "title": "Good view. Better receipt.",
            "body": "One of the few proof photos that also works as a postcard.",
            "image": as_image(scenic, "Scenic drink"),
        },
        {
            "id": "group-toast",
            "layout": "multi-image",
            "kicker": "Group record",
            "title": "Group proof",
            "body": "Everyone appears in the evidence eventually.",
            "images": group_images,
        },
        {
            "id": "locations",
            "layout": "locations",
            "kicker": "Location journey",
            "title": "Tokyo carried it",
            "body": "Side quests still made the map.",
            "image": as_image(locations_image, "Trip location"),
            "locations": locations[:5],
        },
        {
            "id": "photo-wall",
            "layout": "gallery",
            "kicker": "Camera roll evidence",
            "title": "The archive survived",
            "body": "A short scroll through the receipts that made the cut.",
            "images": curated_gallery,
        },
        {
            "id": "finale",
            "layout": "finale",
            "kicker": "Final boarding call",
            "title": "One last Strong Zero",
            "body": "The trip ended here. The spreadsheet made it home.",
            "image": as_image(finale, "Final drink"),
        },
    ]

    data = {
        "meta": {
            "title": "BeerRunJPN Wrapped",
            "subtitle": "The final trip recap",
            "generated_at": datetime.now(UTC).isoformat(),
            "audio_path": DEFAULT_AUDIO_PATH,
            "slide_duration_ms": 10500,
        },
        "stats": {
            "total_entries": len(entries),
            "total_photos": valid_photo_count,
            "total_liters": round(total_liters, 2),
            "total_pure_alcohol": round(total_alcohol, 3),
            "start_date": start_date,
            "end_date": end_date,
            "top_drink": top_drink,
            "top_drink_count": top_drink_count,
        },
        "slides": slides,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return data


def main():
    parser = argparse.ArgumentParser(description="Build BeerRunJPN Wrapped JSON from the trip database.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_PATH), help="Output JSON path")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Project root for validating static images")
    args = parser.parse_args()

    data = build_wrapped_data(db_path=args.db, output_path=args.out, root=args.root)
    print(f"Wrote {args.out} with {len(data['slides'])} slides")


if __name__ == "__main__":
    main()
