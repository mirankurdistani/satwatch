import sqlite3

conn = sqlite3.connect("satwatch.db")
cur = conn.cursor()

# Pc sütunu ekle
try:
    cur.execute("ALTER TABLE conjunction_log ADD COLUMN pc REAL DEFAULT 0")
    print("✅ Pc sütunu eklendi")
except Exception as e:
    print(f"ℹ️  {e}")

# Mevcut kayıtları güncelle
import math

def pc_calc(dist, vel, r=0.01):
    sigma2 = 0.2**2 + 1.0**2 + 0.2**2
    if not dist or dist == 0: return 0
    p = (r**2 / (2*sigma2)) * math.exp(-dist**2 / (2*sigma2))
    vf = max(0.1, min(1.0, 7.5/vel)) if vel and vel > 0 else 1.0
    return min(p*vf, 1.0)

cur.execute("SELECT id, min_distance_km, relative_velocity_kms FROM conjunction_log")
rows = cur.fetchall()
for row in rows:
    pc = pc_calc(row[1], row[2])
    cur.execute("UPDATE conjunction_log SET pc=? WHERE id=?", (pc, row[0]))

conn.commit()
conn.close()
print(f"✅ {len(rows)} kayıt Pc ile güncellendi")
