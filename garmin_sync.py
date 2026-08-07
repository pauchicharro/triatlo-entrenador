"""Sincronitza activitats i mètriques de benestar des de Garmin Connect a data/garmin/."""

import argparse
import csv
import json
import os
from datetime import date, timedelta
from pathlib import Path

import garminconnect
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent / "data" / "garmin"
ACTIVITIES_DIR = DATA_DIR / "activities"
ACTIVITIES_CSV = DATA_DIR / "activities.csv"
WELLNESS_DIR = DATA_DIR / "wellness"
TOKENSTORE = os.path.expanduser("~/.garminconnect")

CSV_FIELDS = [
    "activityId", "activityName", "activityType", "startTimeLocal",
    "distance", "duration", "calories", "averageHR", "maxHR",
    "trainingEffectLabel", "aerobicTrainingEffect", "anaerobicTrainingEffect",
]


def login():
    try:
        client = garminconnect.Garmin()
        client.login(TOKENSTORE)
    except Exception:
        email = os.getenv("GARMIN_EMAIL")
        password = os.getenv("GARMIN_PASSWORD")
        if not email or not password:
            raise SystemExit(
                "Cal GARMIN_EMAIL i GARMIN_PASSWORD a .env per fer el primer login."
            )
        client = garminconnect.Garmin(email=email, password=password)
        client.login()
        client.garth.dump(TOKENSTORE)
    return client


def sync_activities(client, days):
    ACTIVITIES_DIR.mkdir(parents=True, exist_ok=True)

    existing = {}
    if ACTIVITIES_CSV.exists():
        with open(ACTIVITIES_CSV, newline="") as f:
            for row in csv.DictReader(f):
                existing[row["activityId"]] = row

    activities = client.get_activities_by_date(
        (date.today() - timedelta(days=days)).isoformat(), date.today().isoformat()
    )

    for activity in activities:
        activity_id = str(activity["activityId"])
        with open(ACTIVITIES_DIR / f"{activity_id}.json", "w") as f:
            json.dump(activity, f, indent=2)

        existing[activity_id] = {
            "activityId": activity_id,
            "activityName": activity.get("activityName"),
            "activityType": (activity.get("activityType") or {}).get("typeKey"),
            "startTimeLocal": activity.get("startTimeLocal"),
            "distance": activity.get("distance"),
            "duration": activity.get("duration"),
            "calories": activity.get("calories"),
            "averageHR": activity.get("averageHR"),
            "maxHR": activity.get("maxHR"),
            "trainingEffectLabel": activity.get("trainingEffectLabel"),
            "aerobicTrainingEffect": activity.get("aerobicTrainingEffect"),
            "anaerobicTrainingEffect": activity.get("anaerobicTrainingEffect"),
        }

    rows = sorted(existing.values(), key=lambda r: r.get("startTimeLocal") or "")
    with open(ACTIVITIES_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(activities)} activitats revisades, {len(rows)} en total a {ACTIVITIES_CSV}")


def sync_wellness(client, days):
    WELLNESS_DIR.mkdir(parents=True, exist_ok=True)

    for i in range(days):
        day = (date.today() - timedelta(days=i)).isoformat()
        out_path = WELLNESS_DIR / f"{day}.json"
        if out_path.exists():
            continue

        wellness = {}
        for key, fetch in (
            ("sleep", lambda: client.get_sleep_data(day)),
            ("hrv", lambda: client.get_hrv_data(day)),
            ("body_battery", lambda: client.get_body_battery(day, day)),
            ("training_status", lambda: client.get_training_status(day)),
        ):
            try:
                wellness[key] = fetch()
            except Exception as e:
                wellness[key] = {"error": str(e)}

        with open(out_path, "w") as f:
            json.dump(wellness, f, indent=2)

    print(f"Benestar diari sincronitzat a {WELLNESS_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=14, help="Finestra de dies a sincronitzar")
    args = parser.parse_args()

    garmin_client = login()
    sync_activities(garmin_client, args.days)
    sync_wellness(garmin_client, args.days)
