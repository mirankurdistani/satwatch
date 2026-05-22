import sqlite3
import requests
import os
import math
import json
from dotenv import load_dotenv
from sgp4.api import Satrec, jday
from datetime import datetime, timezone, timedelta

load_dotenv()

EMAIL = os.getenv("SPACETRACK_EMAIL")
PASSWORD = os.getenv("SPACETRACK_PASSWORD")
BASE_URL = "https://www.space-track.org"

# ─────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────

def get_session():
    session = requests.Session()
    session.post(f"{BASE_URL}/ajaxauth/login", data={
        "identity": EMAIL, "password": PASSWORD
    })
    return session

def mm_to_alt(mm):
    mu = 398600.4418
    n = mm * 2 * math.pi / 86400
    a = (mu / n**2) ** (1/3)
    return round(a - 6371, 2)

def calc_dv(mm1, mm2):
    mu = 398600.4418
    def v(mm):
        n = mm * 2 * math.pi / 86400
        a = (mu / n**2) ** (1/3)
        return math.sqrt(mu / a)
    return round(abs(v(mm2) - v(mm1)) * 1000, 4)

def get_pos_vel(sat, dt):
    jd, fr = jday(dt.year, dt.month, dt.day,
                  dt.hour, dt.minute, dt.second)
    err, pos, vel = sat.sgp4(jd, fr)
    return (pos, vel) if err == 0 else (None, None)

def dist_km(p1, p2):
    return math.sqrt(sum((a-b)**2 for a,b in zip(p1,p2)))

def rel_vel(v1, v2):
    return math.sqrt(sum((a-b)**2 for a,b in zip(v1,v2)))

def risk_label(d):
    if d < 1:  return "CRITICAL"
    if d < 5:  return "HIGH"
    if d < 20: return "MEDIUM"
    return "LOW"

# ─────────────────────────────────────────
# ADIM 1: VERİ GÜNCELLEME
# ─────────────────────────────────────────

def step1_update_tle(session):
    print("\n📡 ADIM 1: TLE verisi güncelleniyor...")
    url = (f"{BASE_URL}/basicspacedata/query/class/gp"
           f"/OBJECT_NAME/STARLINK~~"
           f"/orderby/NORAD_CAT_ID asc/format/json")
    data = session.get(url).json()

    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()

    new_count = changed = same = 0
    for sat in data:
        cur.execute("SELECT epoch FROM satellites WHERE norad_id=?",
                    (sat.get("NORAD_CAT_ID"),))
        row = cur.fetchone()
        change_type = None
        if not row:
            change_type = "new_satellite"
            new_count += 1
        elif row[0] != sat.get("EPOCH"):
            change_type = "maneuver_candidate"
            changed += 1
        else:
            same += 1

        cur.execute("""
            INSERT OR REPLACE INTO satellites
            (norad_id,name,epoch,mean_motion,eccentricity,
             inclination,raan,tle_line1,tle_line2,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)
        """, (
            sat.get("NORAD_CAT_ID"), sat.get("OBJECT_NAME"),
            sat.get("EPOCH"), float(sat.get("MEAN_MOTION",0)),
            float(sat.get("ECCENTRICITY",0)),
            float(sat.get("INCLINATION",0)),
            float(sat.get("RA_OF_ASC_NODE",0)),
            sat.get("TLE_LINE1"), sat.get("TLE_LINE2"),
            datetime.utcnow().isoformat()
        ))

        if change_type:
            cur.execute("""
                INSERT INTO change_log
                (norad_id,name,change_type,new_epoch,detected_at)
                VALUES(?,?,?,?,?)
            """, (sat.get("NORAD_CAT_ID"), sat.get("OBJECT_NAME"),
                  change_type, sat.get("EPOCH"),
                  datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()
    print(f"   ✅ Aynı: {same} | 🆕 Yeni: {new_count} | 🚀 Değişen: {changed}")
    return changed

# ─────────────────────────────────────────
# ADIM 2: MANEVRA ANALİZİ
# ─────────────────────────────────────────

def step2_maneuver_analysis():
    print("\n🔍 ADIM 2: Manevra analizi...")
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()
    fleet_avg = cur.execute(
        "SELECT AVG(mean_motion) FROM satellites"
    ).fetchone()[0]

    cur.execute("""
        SELECT s.norad_id, s.name, s.mean_motion, s.inclination
        FROM change_log cl
        JOIN satellites s ON cl.norad_id = s.norad_id
        WHERE cl.change_type = 'maneuver_candidate'
        ORDER BY ABS(s.mean_motion - ?) DESC
        LIMIT 10
    """, (fleet_avg,))

    rows = cur.fetchall()
    conn.close()

    deorbit = []
    anomalies = []
    for r in rows:
        alt = mm_to_alt(r[2])
        score = round(abs(r[2] - fleet_avg) * 1000, 2)
        if alt < 300:
            deorbit.append((r[1], alt, score))
        anomalies.append((r[1], alt, score))

    print(f"   📊 Analiz edilen: {len(rows)} yüksek-anomali uydu")
    print(f"   ☄️  Deorbit sürecinde: {len(deorbit)}")
    if anomalies:
        top = anomalies[0]
        print(f"   🏆 En yüksek anomali: {top[0]} "
              f"({top[1]:.1f} km, skor={top[2]})")
    return anomalies

# ─────────────────────────────────────────
# ADIM 3: CONJUNCTION TARAMASI
# ─────────────────────────────────────────

def step3_conjunction_scan():
    print("\n⚠️  ADIM 3: Conjunction taraması...")
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT norad_id, name, tle_line1, tle_line2
        FROM satellites
        WHERE tle_line1 IS NOT NULL
        ORDER BY RANDOM() LIMIT 30
    """)
    sats = cur.fetchall()
    conn.close()

    now = datetime.now(timezone.utc)
    results = []

    for i in range(len(sats)):
        for j in range(i+1, len(sats)):
            s1, s2 = sats[i], sats[j]
            try:
                sat1 = Satrec.twoline2rv(s1[2], s1[3])
                sat2 = Satrec.twoline2rv(s2[2], s2[3])
                min_dist = float("inf")
                min_t = None
                min_rv = None
                t = now
                while t < now + timedelta(hours=24):
                    p1, v1 = get_pos_vel(sat1, t)
                    p2, v2 = get_pos_vel(sat2, t)
                    if p1 and p2:
                        d = dist_km(p1, p2)
                        if d < min_dist:
                            min_dist = d
                            min_t = t
                            min_rv = rel_vel(v1, v2)
                    t += timedelta(seconds=60)

                risk = risk_label(min_dist)
                results.append({
                    "sat1": s1[1], "sat2": s2[1],
                    "dist": round(min_dist, 3),
                    "vel": round(min_rv, 3) if min_rv else 0,
                    "risk": risk, "time": min_t
                })

                if risk in ("CRITICAL","HIGH","MEDIUM"):
                    conn2 = sqlite3.connect("satwatch.db")
                    cur2 = conn2.cursor()
                    cur2.execute("""
                        INSERT INTO conjunction_log
                        (sat1_name,sat2_name,sat1_norad,sat2_norad,
                         min_distance_km,relative_velocity_kms,
                         closest_approach_time,risk_level,scan_time)
                        VALUES(?,?,?,?,?,?,?,?,?)
                    """, (s1[1], s2[1], s1[0], s2[0],
                          round(min_dist,3),
                          round(min_rv,3) if min_rv else 0,
                          min_t.isoformat() if min_t else None,
                          risk, now.isoformat()))
                    conn2.commit()
                    conn2.close()
            except Exception:
                pass

    results.sort(key=lambda x: x["dist"])
    critical = [r for r in results if r["risk"] == "CRITICAL"]
    high     = [r for r in results if r["risk"] == "HIGH"]
    medium   = [r for r in results if r["risk"] == "MEDIUM"]

    print(f"   🔍 {len(results)} çift tarandı")
    print(f"   🔴 Kritik: {len(critical)} | "
          f"🟠 Yüksek: {len(high)} | "
          f"🟡 Orta: {len(medium)}")

    if results:
        top = results[0]
        print(f"   📍 En yakın: {top['sat1']} ↔ {top['sat2']} "
              f"→ {top['dist']} km")
    return results

# ─────────────────────────────────────────
# ADIM 4: RAPOR
# ─────────────────────────────────────────

def step4_report(changed, anomalies, conjunctions):
    print("\n" + "="*55)
    print("📋 SATWATCH GÜNLÜK RAPORU")
    print(f"   {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    print("="*55)

    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM satellites").fetchone()[0]
    total_changes = cur.execute(
        "SELECT COUNT(*) FROM change_log"
    ).fetchone()[0]
    conn.close()

    print(f"  Toplam uydu izleniyor : {total:,}")
    print(f"  Bu turda TLE değişen  : {changed:,}")
    print(f"  Toplam change_log     : {total_changes:,}")

    critical_conj = [c for c in conjunctions if c["risk"] == "CRITICAL"]
    if critical_conj:
        print(f"\n  🚨 KRİTİK CONJUNCTION VAR!")
        for c in critical_conj:
            print(f"     {c['sat1']} ↔ {c['sat2']} → {c['dist']} km")
    else:
        print(f"\n  ✅ Kritik conjunction yok")

    if anomalies:
        print(f"\n  🏆 En anomalik uydu: {anomalies[0][0]}")
        print(f"     İrtifa: {anomalies[0][1]:.1f} km | "
              f"Skor: {anomalies[0][2]}")

    print("\n" + "="*55)
    print("✅ Pipeline tamamlandı.")

# ─────────────────────────────────────────
# ANA ÇALIŞMA
# ─────────────────────────────────────────

if __name__ == "__main__":
    print("🛸 SatWatch Pipeline Başlatıldı")
    print(f"   {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

    session = get_session()
    changed   = step1_update_tle(session)
    anomalies = step2_maneuver_analysis()
    conjs     = step3_conjunction_scan()
    step4_report(changed, anomalies, conjs)
