import sqlite3
import math
from sgp4.api import Satrec, jday
from datetime import datetime, timezone, timedelta

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
    if dist < 1:  return "🔴 KRİTİK"
    if dist < 5:  return "🟠 YÜKSEK"
    if dist < 20: return "🟡 ORTA"
    return "🟢 DÜŞÜK"

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

def load_mixed_satellites():
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()

    groups = []

    # Grup 1: 53° eğim (en kalabalık Starlink kabuğu)
    cur.execute("""
        SELECT norad_id, name, tle_line1, tle_line2, inclination
        FROM satellites
        WHERE tle_line1 IS NOT NULL AND inclination BETWEEN 52 AND 54
        ORDER BY RANDOM() LIMIT 15
    """)
    groups += cur.fetchall()

    # Grup 2: 70° eğim (polar yakını)
    cur.execute("""
        SELECT norad_id, name, tle_line1, tle_line2, inclination
        FROM satellites
        WHERE tle_line1 IS NOT NULL AND inclination BETWEEN 69 AND 71
        ORDER BY RANDOM() LIMIT 10
    """)
    groups += cur.fetchall()

    # Grup 3: 97° eğim (sun-synchronous / polar)
    cur.execute("""
        SELECT norad_id, name, tle_line1, tle_line2, inclination
        FROM satellites
        WHERE tle_line1 IS NOT NULL AND inclination BETWEEN 96 AND 98
        ORDER BY RANDOM() LIMIT 10
    """)
    groups += cur.fetchall()

    conn.close()
    return groups

if __name__ == "__main__":
    print("🛸 SatWatch — Çapraz Yörünge Conjunction Taraması")
    print("   3 farklı orbital shell: 53° | 70° | 97°\n")

    sats = load_mixed_satellites()
    shells = {}
    for s in sats:
        inc = s[4]
        if inc < 60:
            shells.setdefault("53°", []).append(s)
        elif inc < 80:
            shells.setdefault("70°", []).append(s)
        else:
            shells.setdefault("97°", []).append(s)

    for shell, group in shells.items():
        print(f"  Shell {shell}: {len(group)} uydu")

    total_pairs = (len(sats) * (len(sats)-1)) // 2
    print(f"\n🔍 {total_pairs} çift taranıyor (farklı shell'ler arası dahil)...\n")

    results = []
    for i in range(len(sats)):
        for j in range(i+1, len(sats)):
            s1, s2 = sats[i], sats[j]
            try:
                sat1 = Satrec.twoline2rv(s1[2], s1[3])
                sat2 = Satrec.twoline2rv(s2[2], s2[3])
                dist, t, vel = find_conjunction(sat1, sat2)

                inc1 = s1[4]
                inc2 = s2[4]
                cross_shell = abs(inc1 - inc2) > 10

                results.append({
                    "sat1": s1[1], "sat2": s2[1],
                    "min_dist": dist, "time": t,
                    "rel_vel": vel,
                    "risk": risk_level(dist),
                    "cross": "✦" if cross_shell else " "
                })
            except Exception:
                pass

    results.sort(key=lambda x: x["min_dist"])

    print(f"{'='*65}")
    print(f"EN RİSKLİ 20 ÇİFT  (✦ = farklı orbital shell)")
    print(f"{'='*65}")
    print(f"  {'Risk':<12} {'Mesafe':>9} {'Hız':>8}  Çift")
    print(f"  {'-'*12} {'-'*9} {'-'*8}  {'-'*35}")

    for r in results[:20]:
        t_str = r["time"].strftime("%m-%d %H:%M") if r["time"] else "?"
        print(f"  {r['risk']:<12} {r['min_dist']:>7.3f}km "
              f"{r['rel_vel']:>6.2f}km/s {r['cross']} "
              f"{r['sat1']} ↔ {r['sat2']}")

    cross_risks = [r for r in results if r["cross"] == "✦" and r["min_dist"] < 50]
    print(f"\n📊 ÖZET")
    print(f"  Toplam çift         : {len(results)}")
    print(f"  Çapraz shell (<50km): {len(cross_risks)}")
    for level, sym in [("KRİTİK",  "<1km"),
                       ("YÜKSEK",  "<5km"),
                       ("ORTA",    "<20km")]:
        thresholds = {"KRİTİK": 1, "YÜKSEK": 5, "ORTA": 20}
        count = len([r for r in results
                     if r["min_dist"] < thresholds[level]])
        print(f"  {level} ({sym})       : {count}")
