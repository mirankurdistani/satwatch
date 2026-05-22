import sqlite3
import requests
import os
import math
from dotenv import load_dotenv
from datetime import datetime, timezone

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
    return round(a - 6371, 1)

def analyze_maneuvers():
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()

    print("=" * 55)
    print("CHANGE LOG ANALİZİ")
    print("=" * 55)

    cur.execute("SELECT COUNT(*) FROM change_log")
    total = cur.fetchone()[0]
    print(f"  Toplam kayıt        : {total}")

    cur.execute("""
        SELECT COUNT(*) FROM change_log
        WHERE change_type = 'maneuver_candidate'
    """)
    candidates = cur.fetchone()[0]
    print(f"  Manevra adayı       : {candidates}")

    cur.execute("""
        SELECT MIN(detected_at), MAX(detected_at)
        FROM change_log
    """)
    row = cur.fetchone()
    print(f"  İlk tespit          : {row[0][:19]}")
    print(f"  Son tespit          : {row[1][:19]}")

    print("\n" + "=" * 55)
    print("FLAŞT DEĞİŞİM GÖSTEREN UYDULAR (TOP 15)")
    print("  → Bunlar gerçek manevra adayları")
    print("=" * 55)

    cur.execute("""
        SELECT
            cl.name,
            cl.norad_id,
            cl.new_epoch,
            s.mean_motion,
            s.inclination
        FROM change_log cl
        JOIN satellites s ON cl.norad_id = s.norad_id
        WHERE cl.change_type = 'maneuver_candidate'
        ORDER BY cl.new_epoch DESC
        LIMIT 15
    """)

    rows = cur.fetchall()
    print(f"  {'İsim':<22} {'İrtifa':>8} {'Eğim':>7}  Epoch")
    print(f"  {'-'*22} {'-'*8} {'-'*7}  {'-'*19}")
    for row in rows:
        name, norad, epoch, mm, inc = row
        alt = mean_motion_to_altitude(mm)
        print(f"  {name:<22} {alt:>6} km  {inc:>6.2f}°  {epoch[:19]}")

    print("\n" + "=" * 55)
    print("İRTİFA DAĞILIMI (manevra adayları)")
    print("=" * 55)

    cur.execute("""
        SELECT s.mean_motion
        FROM change_log cl
        JOIN satellites s ON cl.norad_id = s.norad_id
        WHERE cl.change_type = 'maneuver_candidate'
    """)
    motions = [r[0] for r in cur.fetchall()]
    altitudes = [mean_motion_to_altitude(m) for m in motions]

    buckets = {
        "300-400 km (çok alçak)": 0,
        "400-500 km (alçak)    ": 0,
        "500-600 km (orta)     ": 0,
        "600+ km   (yüksek)   ": 0,
    }
    for alt in altitudes:
        if alt < 400:
            buckets["300-400 km (çok alçak)"] += 1
        elif alt < 500:
            buckets["400-500 km (alçak)    "] += 1
        elif alt < 600:
            buckets["500-600 km (orta)     "] += 1
        else:
            buckets["600+ km   (yüksek)   "] += 1

    total_b = sum(buckets.values())
    for label, count in buckets.items():
        bar = "█" * int((count / total_b) * 30) if total_b > 0 else ""
        print(f"  {label}: {bar} {count}")

    print("\n" + "=" * 55)
    print("ANOMALİ SKORU (fleet ortalamasından sapma)")
    print("=" * 55)

    cur.execute("SELECT AVG(mean_motion) FROM satellites")
    fleet_avg = cur.fetchone()[0]
    fleet_alt = mean_motion_to_altitude(fleet_avg)
    print(f"  Filo ort. irtifası  : {fleet_alt} km")

    cur.execute("""
        SELECT s.name, s.mean_motion, s.inclination
        FROM change_log cl
        JOIN satellites s ON cl.norad_id = s.norad_id
        WHERE cl.change_type = 'maneuver_candidate'
        ORDER BY ABS(s.mean_motion - ?) DESC
        LIMIT 10
    """, (fleet_avg,))

    print(f"\n  En yüksek anomali skoru (ortalamasından en çok sapan):")
    print(f"  {'İsim':<22} {'İrtifa':>8}  Skor")
    print(f"  {'-'*22} {'-'*8}  {'-'*10}")
    for row in cur.fetchall():
        name, mm, inc = row
        alt = mean_motion_to_altitude(mm)
        score = round(abs(mm - fleet_avg) * 1000, 2)
        bar = "▓" * min(int(score / 5), 20)
        print(f"  {name:<22} {alt:>6} km  {bar} {score}")

    conn.close()
    print(f"\n✅ Analiz tamamlandı: {datetime.utcnow().strftime('%H:%M:%S')} UTC")
    print("💡 Yüksek anomali skoru = yörünge değişimi büyük = manevra olası")

if __name__ == "__main__":
    analyze_maneuvers()
