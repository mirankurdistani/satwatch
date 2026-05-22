import requests
import sqlite3
import json
import os
import time
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

EMAIL = os.getenv("SPACETRACK_EMAIL")
PASSWORD = os.getenv("SPACETRACK_PASSWORD")
BASE_URL = "https://www.space-track.org"

def get_session():
    session = requests.Session()
    session.post(f"{BASE_URL}/ajaxauth/login", data={
        "identity": EMAIL,
        "password": PASSWORD
    })
    return session

def fetch_starlink(session):
    url = (
        f"{BASE_URL}/basicspacedata/query/class/gp"
        f"/OBJECT_NAME/STARLINK~~"
        f"/orderby/NORAD_CAT_ID asc"
        f"/format/json"
    )
    response = session.get(url)
    return response.json()

def detect_changes(cur, sat):
    cur.execute(
        "SELECT tle_line1, tle_line2, epoch FROM satellites WHERE norad_id = ?",
        (sat.get("NORAD_CAT_ID"),)
    )
    row = cur.fetchone()
    if not row:
        return "new"
    old_line1, old_line2, old_epoch = row
    if sat.get("EPOCH") != old_epoch:
        return "changed"
    return "same"

def save_change_log(cur, sat, change_type):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            norad_id TEXT,
            name TEXT,
            change_type TEXT,
            old_epoch TEXT,
            new_epoch TEXT,
            detected_at TEXT
        )
    """)
    cur.execute("""
        INSERT INTO change_log (norad_id, name, change_type, new_epoch, detected_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        sat.get("NORAD_CAT_ID"),
        sat.get("OBJECT_NAME"),
        change_type,
        sat.get("EPOCH"),
        datetime.utcnow().isoformat()
    ))

def update_satellite(cur, sat):
    cur.execute("""
        INSERT OR REPLACE INTO satellites
        (norad_id, name, epoch, mean_motion, eccentricity,
         inclination, raan, tle_line1, tle_line2, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sat.get("NORAD_CAT_ID"),
        sat.get("OBJECT_NAME"),
        sat.get("EPOCH"),
        float(sat.get("MEAN_MOTION", 0)),
        float(sat.get("ECCENTRICITY", 0)),
        float(sat.get("INCLINATION", 0)),
        float(sat.get("RA_OF_ASC_NODE", 0)),
        sat.get("TLE_LINE1"),
        sat.get("TLE_LINE2"),
        datetime.utcnow().isoformat()
    ))

def run_update():
    print(f"\n🔄 Güncelleme başladı: {datetime.utcnow().strftime('%H:%M:%S')} UTC")
    session = get_session()
    data = fetch_starlink(session)

    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()

    new_count = 0
    changed_count = 0
    same_count = 0

    for sat in data:
        change = detect_changes(cur, sat)
        if change == "changed":
            save_change_log(cur, sat, "maneuver_candidate")
            changed_count += 1
        elif change == "new":
            save_change_log(cur, sat, "new_satellite")
            new_count += 1
        else:
            same_count += 1
        update_satellite(cur, sat)

    conn.commit()

    print(f"  ✅ Aynı kalan  : {same_count}")
    print(f"  🆕 Yeni uydu   : {new_count}")
    print(f"  🚀 TLE değişti : {changed_count} ← manevra adayı!")

    if changed_count > 0:
        print(f"\n  📋 Manevra adayları:")
        cur.execute("""
            SELECT name, new_epoch, detected_at
            FROM change_log
            WHERE change_type = 'maneuver_candidate'
            ORDER BY detected_at DESC
            LIMIT 10
        """)
        for row in cur.fetchall():
            print(f"     {row[0]:25} | epoch: {row[1][:19]}")

    conn.close()
    print(f"\n⏳ Sonraki güncelleme 6 saat sonra...")

if __name__ == "__main__":
    print("🛸 SatWatch Scheduler başlatıldı")
    print("   Ctrl+C ile durdurabilirsin\n")
    run_update()
