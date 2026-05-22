import sqlite3
import math

def mm_to_alt(mm):
    mu = 398600.4418
    n = mm * 2 * math.pi / 86400
    a = (mu / n**2) ** (1/3)
    return round(a - 6371, 2)

conn = sqlite3.connect("satwatch.db")
cur = conn.cursor()

fleet_avg = cur.execute("SELECT AVG(mean_motion) FROM satellites").fetchone()[0]

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

print("🔍 ADIM 2: Manevra analizi")
print(f"{'='*55}")
print(f"  Filo ort. irtifası: {mm_to_alt(fleet_avg):.1f} km\n")
print(f"  {'Uydu':<22} {'İrtifa':>8}  {'Skor':>8}  Durum")
print(f"  {'-'*22} {'-'*8}  {'-'*8}  {'-'*10}")

deorbit = []
for r in rows:
    alt = mm_to_alt(r[2])
    score = round(abs(r[2] - fleet_avg) * 1000, 2)
    status = "☄️ DEORBİT" if alt < 300 else "🚀 Manevra"
    if alt < 300:
        deorbit.append(r[1])
    print(f"  {r[1]:<22} {alt:>7.1f}km  {score:>8.2f}  {status}")

print(f"\n  Toplam analiz   : {len(rows)}")
print(f"  Deorbit adayı   : {len(deorbit)}")
if deorbit:
    print(f"  Deorbit uydular : {', '.join(deorbit)}")
