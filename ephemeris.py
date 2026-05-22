import requests
import sqlite3
import os
import math
import pandas as pd
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

def fetch_gp_history(session, norad_id, days=7):
    """Bir uydunun son N günlük TLE geçmişini çek"""
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = (
        f"{BASE_URL}/basicspacedata/query/class/gp_history"
        f"/NORAD_CAT_ID/{norad_id}"
        f"/EPOCH/%3E{since}"
        f"/orderby/EPOCH asc"
        f"/format/json"
    )
    response = session.get(url)
    return response.json()

def mean_motion_to_altitude(mm):
    mu = 398600.4418
    n = mm * 2 * math.pi / 86400
    a = (mu / n**2) ** (1/3)
    return round(a - 6371, 2)

def calculate_delta_v(mm1, mm2):
    """
    İki mean motion arasındaki farktan yaklaşık delta-v hesapla
    Vis-viva denklemi kullanılır
    """
    mu = 398600.4418

    def mm_to_v(mm):
        n = mm * 2 * math.pi / 86400
        a = (mu / n**2) ** (1/3)
        return math.sqrt(mu / a)

    v1 = mm_to_v(mm1)
    v2 = mm_to_v(mm2)
    delta_v = abs(v2 - v1) * 1000  # m/s
    return round(delta_v, 4)

def analyze_satellite(norad_id, name):
    print(f"\n{'='*55}")
    print(f"UYDU: {name} (NORAD: {norad_id})")
    print(f"{'='*55}")

    session = get_session()
    history = fetch_gp_history(session, norad_id, days=7)

    if not history:
        print("❌ Veri bulunamadı.")
        return

    print(f"✅ {len(history)} adet TLE kaydı bulundu (son 7 gün)\n")

    print(f"  {'Epoch':<22} {'İrtifa':>9} {'Tur/gün':>9} {'Δ İrtifa':>10} {'Δv (m/s)':>10}")
    print(f"  {'-'*22} {'-'*9} {'-'*9} {'-'*10} {'-'*10}")

    prev = None
    maneuvers = []

    for rec in history:
        mm = float(rec["MEAN_MOTION"])
        alt = mean_motion_to_altitude(mm)
        epoch = rec["EPOCH"][:19]

        if prev:
            prev_mm = float(prev["MEAN_MOTION"])
            prev_alt = mean_motion_to_altitude(prev_mm)
            delta_alt = round(alt - prev_alt, 2)
            dv = calculate_delta_v(prev_mm, mm)

            arrow = ""
            if abs(delta_alt) > 1:
                arrow = "⬆️" if delta_alt > 0 else "⬇️"
                maneuvers.append({
                    "epoch": epoch,
                    "alt": alt,
                    "delta_alt": delta_alt,
                    "dv": dv
                })

            print(f"  {epoch:<22} {alt:>8.2f}km {mm:>9.5f} {delta_alt:>+10.2f} {dv:>10.4f} {arrow}")
        else:
            print(f"  {epoch:<22} {alt:>8.2f}km {mm:>9.5f} {'—':>10} {'—':>10}")

        prev = rec

    print(f"\n{'='*55}")
    print(f"SONUÇ: {len(maneuvers)} manevra tespit edildi")
    if maneuvers:
        total_dv = sum(m["dv"] for m in maneuvers)
        print(f"Toplam delta-v  : {total_dv:.4f} m/s")
        print(f"En büyük irtifa değişimi: {max(abs(m['delta_alt']) for m in maneuvers):.2f} km")
        print("\nManevra detayları:")
        for m in maneuvers:
            direction = "yükselme" if m["delta_alt"] > 0 else "alçalma"
            print(f"  {m['epoch']} → {abs(m['delta_alt']):.2f} km {direction}, Δv={m['dv']:.4f} m/s")

if __name__ == "__main__":
    # En yüksek anomali skorlu uydular
    targets = [
        ("40967", "STARLINK-1816"),
        ("47688", "STARLINK-2249"),
    ]

    for norad_id, name in targets:
        analyze_satellite(norad_id, name)
