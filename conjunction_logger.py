import sqlite3
import math
import os
import requests
import smtplib
from dotenv import load_dotenv
from sgp4.api import Satrec, jday
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText

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

def setup_db():
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conjunction_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sat1_name TEXT,
            sat2_name TEXT,
            sat1_norad TEXT,
            sat2_norad TEXT,
            min_distance_km REAL,
            relative_velocity_kms REAL,
            closest_approach_time TEXT,
            risk_level TEXT,
            scan_time TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("✅ conjunction_log tablosu hazır")

def get_position(sat, dt):
    jd, fr = jday(dt.year, dt.month, dt.day,
                  dt.hour, dt.minute, dt.second)
    err, pos, vel = sat.sgp4(jd, fr)
    if err != 0:
        return None, None
    return pos, vel

def distance_km(p1, p2):
    return math.sqrt(sum((a-b)**2 for a, b in zip(p1, p2)))

def rel_velocity(v1, v2):
    return math.sqrt(sum((a-b)**2 for a, b in zip(v1, v2)))

def risk_level(dist):
    if dist < 1:   return "CRITICAL"
    if dist < 5:   return "HIGH"
    if dist < 20:  return "MEDIUM"
    return "LOW"

def find_conjunction(sat1, sat2, hours=24, step=60):
    now = datetime.now(timezone.utc)
    min_dist = float("inf")
    min_time = None
    min_vel = None
    t = now
    while t < now + timedelta(hours=hours):
        p1, v1 = get_position(sat1, t)
        p2, v2 = get_position(sat2, t)
        if p1 and p2:
            d = distance_km(p1, p2)
            if d < min_dist:
                min_dist = d
                min_time = t
                min_vel = rel_velocity(v1, v2)
        t += timedelta(seconds=step)
    return round(min_dist, 3), min_time, round(min_vel, 3) if min_vel else 0

def load_satellites(limit=40):
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT norad_id, name, tle_line1, tle_line2
        FROM satellites
        WHERE tle_line1 IS NOT NULL
          AND tle_line2 IS NOT NULL
          AND mean_motion BETWEEN 15.0 AND 15.6
          AND inclination BETWEEN 52 AND 54
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

def save_results(results):
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()
    scan_time = datetime.utcnow().isoformat()
    saved = 0
    for r in results:
        if r["risk"] in ("CRITICAL", "HIGH", "MEDIUM"):
            cur.execute("""
                INSERT INTO conjunction_log
                (sat1_name, sat2_name, sat1_norad, sat2_norad,
                 min_distance_km, relative_velocity_kms,
                 closest_approach_time, risk_level, scan_time)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                r["sat1"], r["sat2"],
                r["norad1"], r["norad2"],
                r["min_dist"], r["rel_vel"],
                r["time"].isoformat() if r["time"] else None,
                r["risk"], scan_time
            ))
            saved += 1
    conn.commit()
    conn.close()
    return saved

def print_summary(results):
    by_risk = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    for r in results:
        by_risk[r["risk"]].append(r)

    print(f"\n{'='*60}")
    print("CONJUNCTION TARAMA RAPORU")
    print(f"{'='*60}")
    print(f"  🔴 Kritik (<1 km)   : {len(by_risk['CRITICAL'])}")
    print(f"  🟠 Yüksek (<5 km)   : {len(by_risk['HIGH'])}")
    print(f"  🟡 Orta (<20 km)    : {len(by_risk['MEDIUM'])}")
    print(f"  🟢 Düşük            : {len(by_risk['LOW'])}")

    for level in ["CRITICAL", "HIGH", "MEDIUM"]:
        if by_risk[level]:
            icons = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}
            print(f"\n{icons[level]} {level} RİSK:")
            for r in by_risk[level]:
                t = r["time"].strftime("%m-%d %H:%M UTC") if r["time"] else "?"
                print(f"   {r['sat1']:20} ↔ {r['sat2']:20}")
                print(f"   Mesafe: {r['min_dist']:.3f} km | "
                      f"Hız: {r['rel_vel']:.2f} km/s | "
                      f"Zaman: {t}")

def run_scan():
    print(f"🛸 SatWatch Conjunction Taraması")
    print(f"   {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")

    setup_db()
    sats = load_satellites(limit=40)
    print(f"✅ {len(sats)} uydu yüklendi")

    total_pairs = (len(sats) * (len(sats)-1)) // 2
    print(f"🔍 {total_pairs} çift taranıyor...\n")

    results = []
    for i in range(len(sats)):
        for j in range(i+1, len(sats)):
            s1, s2 = sats[i], sats[j]
            try:
                sat1 = Satrec.twoline2rv(s1[2], s1[3])
                sat2 = Satrec.twoline2rv(s2[2], s2[3])
                dist, t, vel = find_conjunction(sat1, sat2)
                results.append({
                    "sat1": s1[1], "sat2": s2[1],
                    "norad1": s1[0], "norad2": s2[0],
                    "min_dist": dist, "time": t,
                    "rel_vel": vel,
                    "risk": risk_level(dist)
                })
            except Exception:
                pass

    results.sort(key=lambda x: x["min_dist"])
    print_summary(results)

    saved = save_results(results)
    print(f"\n💾 {saved} kayıt veritabanına eklendi (MEDIUM+ riskler)")

    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM conjunction_log")
    total = cur.fetchone()[0]
    cur.execute("""
        SELECT risk_level, COUNT(*) FROM conjunction_log
        GROUP BY risk_level ORDER BY COUNT(*) DESC
    """)
    breakdown = cur.fetchall()
    conn.close()

    print(f"\n📊 Toplam conjunction_log kaydı: {total}")
    for row in breakdown:
        print(f"   {row[0]:10}: {row[1]}")

if __name__ == "__main__":
    run_scan()
