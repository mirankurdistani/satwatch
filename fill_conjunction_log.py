import sqlite3
import math
from sgp4.api import Satrec, jday
from datetime import datetime, timezone, timedelta

def get_position(sat, dt):
    jd, fr = jday(dt.year, dt.month, dt.day,
                  dt.hour, dt.minute, dt.second)
    err, pos, vel = sat.sgp4(jd, fr)
    return (pos, vel) if err == 0 else (None, None)

def distance_km(p1, p2):
    return math.sqrt(sum((a-b)**2 for a, b in zip(p1, p2)))

def rel_velocity(v1, v2):
    return math.sqrt(sum((a-b)**2 for a, b in zip(v1, v2)))

def pc_calc(dist, vel, r=0.01):
    sigma2 = 0.2**2 + 1.0**2 + 0.2**2
    if not dist or dist == 0: return 0
    p = (r**2 / (2*sigma2)) * math.exp(-dist**2 / (2*sigma2))
    vf = max(0.1, min(1.0, 7.5/vel)) if vel and vel > 0 else 1.0
    return min(p*vf, 1.0)

def risk_label(d):
    if d < 1:   return "CRITICAL"
    if d < 5:   return "HIGH"
    if d < 20:  return "MEDIUM"
    if d < 100: return "LOW-WATCH"
    return "LOW"

conn = sqlite3.connect("satwatch.db")
cur = conn.cursor()
cur.execute("""
    SELECT norad_id, name, tle_line1, tle_line2
    FROM satellites
    WHERE tle_line1 IS NOT NULL
    ORDER BY RANDOM() LIMIT 60
""")
sats = cur.fetchall()

now = datetime.now(timezone.utc)
scan_time = now.isoformat()
saved = 0

print(f"🔍 {len(sats)} uydu, {len(sats)*(len(sats)-1)//2} çift taranıyor...")

for i in range(len(sats)):
    for j in range(i+1, len(sats)):
        s1, s2 = sats[i], sats[j]
        try:
            sat1 = Satrec.twoline2rv(s1[2], s1[3])
            sat2 = Satrec.twoline2rv(s2[2], s2[3])
            min_dist = float("inf")
            min_time = None
            min_vel = None
            t = now
            while t < now + timedelta(hours=24):
                p1, v1 = get_position(sat1, t)
                p2, v2 = get_position(sat2, t)
                if p1 and p2:
                    d = distance_km(p1, p2)
                    if d < min_dist:
                        min_dist = d
                        min_time = t
                        min_vel = rel_velocity(v1, v2)
                t += timedelta(seconds=60)

            risk = risk_label(min_dist)
            pc = pc_calc(min_dist, min_vel or 7.5)

            # LOW-WATCH ve üzerini kaydet
            if risk != "LOW":
                cur.execute("""
                    INSERT INTO conjunction_log
                    (sat1_name, sat2_name, sat1_norad, sat2_norad,
                     min_distance_km, relative_velocity_kms,
                     closest_approach_time, risk_level, scan_time, pc)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                """, (
                    s1[1], s2[1], s1[0], s2[0],
                    round(min_dist, 3),
                    round(min_vel, 3) if min_vel else 0,
                    min_time.isoformat() if min_time else None,
                    risk, scan_time, pc
                ))
                saved += 1
        except Exception:
            pass

conn.commit()
conn.close()
print(f"✅ {saved} kayıt conjunction_log'a eklendi")
