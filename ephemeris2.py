import requests
import sqlite3
import os
import math
from dotenv import load_dotenv
from datetime import datetime, timedelta

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

def mean_motion_to_altitude(mm):
    mu = 398600.4418
    n = mm * 2 * math.pi / 86400
    a = (mu / n**2) ** (1/3)
    return round(a - 6371, 3)

def calculate_delta_v(mm1, mm2):
    mu = 398600.4418
    def mm_to_v(mm):
        n = mm * 2 * math.pi / 86400
        a = (mu / n**2) ** (1/3)
        return math.sqrt(mu / a)
    return round(abs(mm_to_v(mm2) - mm_to_v(mm1)) * 1000, 4)

def fetch_gp_history(session, norad_id, days=7):
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = (
        f"{BASE_URL}/basicspacedata/query/class/gp_history"
        f"/NORAD_CAT_ID/{norad_id}"
        f"/EPOCH/%3E{since}"
        f"/orderby/EPOCH asc"
        f"/format/json"
    )
    return session.get(url).json()

def analyze(norad_id, name, session, threshold_km=0.05):
    history = fetch_gp_history(session, norad_id, days=7)
    if not history or len(history) < 2:
        return None

    maneuvers = []
    prev = None
    for rec in history:
        if prev:
            mm1 = float(prev["MEAN_MOTION"])
            mm2 = float(rec["MEAN_MOTION"])
            delta_alt = mean_motion_to_altitude(mm2) - mean_motion_to_altitude(mm1)
            dv = calculate_delta_v(mm1, mm2)
            if abs(delta_alt) >= threshold_km:
                maneuvers.append({
                    "epoch": rec["EPOCH"][:19],
                    "alt": mean_motion_to_altitude(mm2),
                    "delta_alt": round(delta_alt, 3),
                    "dv_ms": dv
                })
        prev = rec

    return {
        "name": name,
        "norad_id": norad_id,
        "records": len(history),
        "maneuvers": maneuvers,
        "current_alt": mean_motion_to_altitude(float(history[-1]["MEAN_MOTION"]))
    }

if __name__ == "__main__":
    # Veritabanından manevra adaylarını çek
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT s.norad_id, s.name, s.mean_motion
        FROM change_log cl
        JOIN satellites s ON cl.norad_id = s.norad_id
        WHERE cl.change_type = 'maneuver_candidate'
        ORDER BY ABS(s.mean_motion - 15.42) DESC
        LIMIT 8
    """)
    targets = cur.fetchall()
    conn.close()

    session = get_session()
    print("🔍 GP Geçmişi Analizi — Son 7 Gün")
    print(f"   Eşik: ≥0.05 km irtifa değişimi\n")

    all_results = []
    for norad_id, name, mm in targets:
        result = analyze(norad_id, name, session)
        if result:
            all_results.append(result)
            m_count = len(result["maneuvers"])
            print(f"  {'✅' if m_count > 0 else '➖'} {name:<22} "
                  f"{result['current_alt']:>7.1f} km  "
                  f"{result['records']:>3} kayıt  "
                  f"{m_count:>2} manevra")

    print(f"\n{'='*55}")
    print("MANEVRA DETAYLARI")
    print(f"{'='*55}")

    for r in all_results:
        if r["maneuvers"]:
            print(f"\n🚀 {r['name']} ({r['norad_id']})")
            for m in r["maneuvers"]:
                direction = "⬆️ yükselme" if m["delta_alt"] > 0 else "⬇️ alçalma"
                print(f"   {m['epoch']}  "
                      f"{abs(m['delta_alt']):.3f} km {direction}  "
                      f"Δv={m['dv_ms']:.4f} m/s")
