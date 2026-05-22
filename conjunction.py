import sqlite3
import math
import os
import requests
from dotenv import load_dotenv
from sgp4.api import Satrec, jday
from datetime import datetime, timezone, timedelta

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

def tle_to_satrec(tle1, tle2):
    return Satrec.twoline2rv(tle1, tle2)

def get_position(sat, dt):
    jd, fr = jday(dt.year, dt.month, dt.day,
                  dt.hour, dt.minute, dt.second + dt.microsecond/1e6)
    err, pos, vel = sat.sgp4(jd, fr)
    if err != 0:
        return None, None
    return pos, vel

def distance_km(pos1, pos2):
    return math.sqrt(sum((a-b)**2 for a, b in zip(pos1, pos2)))

def relative_velocity(vel1, vel2):
    return math.sqrt(sum((a-b)**2 for a, b in zip(vel1, vel2)))

def risk_level(dist_km):
    if dist_km < 1:
        return "🔴 KRİTİK"
    elif dist_km < 5:
        return "🟠 YÜKSEK"
    elif dist_km < 20:
        return "🟡 ORTA"
    else:
        return "🟢 DÜŞÜK"

def find_conjunction(sat1, sat2, hours=24, step_seconds=30):
    """İki uydu arasındaki minimum mesafeyi bul"""
    now = datetime.now(timezone.utc)
    min_dist = float("inf")
    min_time = None
    min_vel = None

    t = now
    end = now + timedelta(hours=hours)

    while t < end:
        pos1, vel1 = get_position(sat1, t)
        pos2, vel2 = get_position(sat2, t)

        if pos1 and pos2:
            dist = distance_km(pos1, pos2)
            if dist < min_dist:
                min_dist = dist
                min_time = t
                min_vel = relative_velocity(vel1, vel2)

        t += timedelta(seconds=step_seconds)

    return min_dist, min_time, min_vel

def load_satellites_from_db(limit=50):
    """Veritabanından benzer yörüngedeki uyduları çek"""
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT norad_id, name, tle_line1, tle_line2,
               mean_motion, inclination
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

if __name__ == "__main__":
    print("🛸 SatWatch — Conjunction Risk Hesaplayıcı")
    print("   Zaman penceresi: önümüzdeki 24 saat")
    print("   Adım: 30 saniye\n")

    satellites = load_satellites_from_db(limit=30)
    print(f"✅ {len(satellites)} uydu yüklendi (benzer yörünge: ~53°, ~550 km)\n")

    results = []
    total_pairs = (len(satellites) * (len(satellites)-1)) // 2
    checked = 0

    print(f"🔍 {total_pairs} çift kontrol ediliyor...\n")

    for i in range(len(satellites)):
        for j in range(i+1, len(satellites)):
            s1 = satellites[i]
            s2 = satellites[j]

            try:
                sat1 = tle_to_satrec(s1[2], s1[3])
                sat2 = tle_to_satrec(s2[2], s2[3])
                min_dist, min_time, rel_vel = find_conjunction(
                    sat1, sat2, hours=24, step_seconds=60
                )

                results.append({
                    "sat1": s1[1],
                    "sat2": s2[1],
                    "min_dist": round(min_dist, 3),
                    "time": min_time,
                    "rel_vel": round(rel_vel, 2) if rel_vel else 0,
                    "risk": risk_level(min_dist)
                })
                checked += 1
            except Exception:
                pass

    results.sort(key=lambda x: x["min_dist"])

    print(f"{'='*65}")
    print(f"CONJUNCTION RAPORU — En Riskli 20 Çift")
    print(f"{'='*65}")
    print(f"  {'Risk':<12} {'Mesafe':>9} {'Hız':>9}  Uydu Çifti")
    print(f"  {'-'*12} {'-'*9} {'-'*9}  {'-'*30}")

    for r in results[:20]:
        t_str = r["time"].strftime("%m-%d %H:%M") if r["time"] else "?"
        print(f"  {r['risk']:<12} {r['min_dist']:>7.3f}km "
              f"{r['rel_vel']:>7.2f}km/s  "
              f"{r['sat1']} ↔ {r['sat2']}")

    critical = [r for r in results if r["min_dist"] < 5]
    print(f"\n📊 ÖZET")
    print(f"  Toplam çift kontrol : {checked}")
    print(f"  Kritik (<1 km)      : {len([r for r in results if r['min_dist'] < 1])}")
    print(f"  Yüksek risk (<5 km) : {len([r for r in results if r['min_dist'] < 5])}")
    print(f"  Orta risk (<20 km)  : {len([r for r in results if r['min_dist'] < 20])}")
