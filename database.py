import sqlite3
import json
from datetime import datetime

def create_db():
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS satellites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            norad_id TEXT UNIQUE,
            name TEXT,
            epoch TEXT,
            mean_motion REAL,
            eccentricity REAL,
            inclination REAL,
            raan REAL,
            tle_line1 TEXT,
            tle_line2 TEXT,
            updated_at TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Veritabanı oluşturuldu: satwatch.db")

def load_from_json():
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()

    with open("starlink_data.json") as f:
        data = json.load(f)

    count = 0
    for sat in data:
        try:
            cur.execute("""
                INSERT OR REPLACE INTO satellites
                (norad_id, name, epoch, mean_motion, eccentricity,
                 inclination, raan, tle_line1, tle_line2, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sat.get("NORAD_CAT_ID"),
                sat.get("OBJECT_NAME"),
                sat.get("EPOCH"),
                float(sat.get("MEAN_MOTION", 0)),
                float(sat.get("ECCENTRICITY", 0)),
                float(sat.get("INCLINATION", 0)),
                float(sat.get("RA_OF_ASC_NODE", 0)),
                sat.get("TLE_LINE1"),
                sat.get("TLE_LINE2"),
                datetime.utcnow().isoformat()
            ))
            count += 1
        except Exception as e:
            print(f"  ⚠️  Hata: {sat.get('OBJECT_NAME')} — {e}")

    conn.commit()
    conn.close()
    print(f"✅ {count} uydu veritabanına kaydedildi.")

def query_examples():
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()

    print("\n📊 VERİTABANI İSTATİSTİKLERİ")
    print("=" * 40)

    cur.execute("SELECT COUNT(*) FROM satellites")
    print(f"  Toplam uydu     : {cur.fetchone()[0]}")

    cur.execute("SELECT AVG(inclination) FROM satellites")
    print(f"  Ort. eğim açısı : {cur.fetchone()[0]:.2f}°")

    cur.execute("SELECT AVG(mean_motion) FROM satellites")
    print(f"  Ort. tur/gün    : {cur.fetchone()[0]:.4f}")

    print("\n🔍 EN YÜKSEK İRTİFALI 5 STARLINK")
    print("=" * 40)
    cur.execute("""
        SELECT name, mean_motion, inclination
        FROM satellites
        ORDER BY mean_motion ASC
        LIMIT 5
    """)
    for row in cur.fetchall():
        print(f"  {row[0]:25} | {row[1]:.4f} tur/gün | {row[2]:.2f}°")

    print("\n🔍 EN DÜŞÜK İRTİFALI 5 STARLINK (debris riski)")
    print("=" * 40)
    cur.execute("""
        SELECT name, mean_motion, inclination
        FROM satellites
        ORDER BY mean_motion DESC
        LIMIT 5
    """)
    for row in cur.fetchall():
        print(f"  {row[0]:25} | {row[1]:.4f} tur/gün | {row[2]:.2f}°")

    conn.close()

if __name__ == "__main__":
    create_db()
    load_from_json()
    query_examples()
