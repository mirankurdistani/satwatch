import sqlite3
import math
import asyncio
import time
from sgp4.api import Satrec, jday
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

def get_position(sat, dt):
    jd, fr = jday(dt.year, dt.month, dt.day,
                  dt.hour, dt.minute, dt.second)
    err, pos, vel = sat.sgp4(jd, fr)
    return (pos, vel) if err == 0 else (None, None)

def distance_km(p1, p2):
    return math.sqrt(sum((a-b)**2 for a, b in zip(p1, p2)))

def rel_velocity(v1, v2):
    return math.sqrt(sum((a-b)**2 for a, b in zip(v1, v2)))

def risk_label(d):
    if d < 1:  return "CRITICAL"
    if d < 5:  return "HIGH"
    if d < 20: return "MEDIUM"
    return "LOW"

def compute_pair(args):
    """Tek bir çift için conjunction hesapla — thread'de çalışır"""
    s1, s2, hours, step = args
    try:
        sat1 = Satrec.twoline2rv(s1[2], s1[3])
        sat2 = Satrec.twoline2rv(s2[2], s2[3])
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
        return {
            "sat1": s1[1], "sat2": s2[1],
            "norad1": s1[0], "norad2": s2[0],
            "min_dist": round(min_dist, 3),
            "time": min_time,
            "rel_vel": round(min_vel, 3) if min_vel else 0,
            "risk": risk_label(min_dist)
        }
    except Exception:
        return None

def load_satellites(limit=60):
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT norad_id, name, tle_line1, tle_line2
        FROM satellites
        WHERE tle_line1 IS NOT NULL
          AND tle_line2 IS NOT NULL
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

async def scan_async(sats, hours=24, step=60, max_workers=8):
    """Tüm çiftleri paralel olarak tara"""
    pairs = [
        (sats[i], sats[j], hours, step)
        for i in range(len(sats))
        for j in range(i+1, len(sats))
    ]

    loop = asyncio.get_event_loop()
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            loop.run_in_executor(executor, compute_pair, pair)
            for pair in pairs
        ]
        completed = await asyncio.gather(*futures)
        results = [r for r in completed if r is not None]

    return results

async def main():
    print("🛸 SatWatch — Async Conjunction Tarayıcı")
    print(f"   {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")

    sats = load_satellites(limit=60)
    total_pairs = (len(sats) * (len(sats)-1)) // 2
    print(f"✅ {len(sats)} uydu yüklendi")
    print(f"🔍 {total_pairs} çift taranacak\n")

    # SENKRON (eski yöntem) hız testi
    print("⏱  Senkron tarama (ilk 10 çift)...")
    t0 = time.time()
    sync_results = []
    test_pairs = [
        (sats[i], sats[j], 24, 60)
        for i in range(5)
        for j in range(i+1, 5)
    ]
    for pair in test_pairs:
        r = compute_pair(pair)
        if r:
            sync_results.append(r)
    sync_time = time.time() - t0
    print(f"   {len(test_pairs)} çift → {sync_time:.2f} saniye")
    print(f"   Tahmini tam tarama: {sync_time/len(test_pairs)*total_pairs:.1f} saniye\n")

    # ASYNC (yeni yöntem) hız testi
    print("⚡ Async tarama (tüm çiftler)...")
    t1 = time.time()
    results = await scan_async(sats, hours=24, step=60, max_workers=8)
    async_time = time.time() - t1
    print(f"   {len(results)} çift → {async_time:.2f} saniye")
    print(f"   Hız artışı: {(sync_time/len(test_pairs)*total_pairs/async_time):.1f}x\n")

    results.sort(key=lambda x: x["min_dist"])

    by_risk = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    for r in results:
        by_risk[r["risk"]].append(r)

    print(f"{'='*55}")
    print(f"CONJUNCTION RAPORU — {len(sats)} uydu, {total_pairs} çift")
    print(f"{'='*55}")
    print(f"  🔴 Kritik (<1 km)  : {len(by_risk['CRITICAL'])}")
    print(f"  🟠 Yüksek (<5 km)  : {len(by_risk['HIGH'])}")
    print(f"  🟡 Orta (<20 km)   : {len(by_risk['MEDIUM'])}")
    print(f"  🟢 Düşük           : {len(by_risk['LOW'])}")

    print(f"\n📍 En yakın 10 çift:")
    print(f"  {'Mesafe':>9}  {'Risk':<10}  Çift")
    print(f"  {'-'*9}  {'-'*10}  {'-'*35}")
    for r in results[:10]:
        print(f"  {r['min_dist']:>7.3f}km  {r['risk']:<10}  "
              f"{r['sat1']} ↔ {r['sat2']}")

    # Veritabanına kaydet
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
                VALUES(?,?,?,?,?,?,?,?,?)
            """, (
                r["sat1"], r["sat2"], r["norad1"], r["norad2"],
                r["min_dist"], r["rel_vel"],
                r["time"].isoformat() if r["time"] else None,
                r["risk"], scan_time
            ))
            saved += 1
    conn.commit()
    conn.close()
    print(f"\n💾 {saved} yüksek-riskli kayıt veritabanına eklendi")
    print(f"⚡ Toplam süre: {async_time:.2f} saniye")

if __name__ == "__main__":
    asyncio.run(main())
