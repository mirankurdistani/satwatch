import requests
import os
from dotenv import load_dotenv
from sgp4.api import Satrec, jday
from datetime import datetime, timezone

load_dotenv()

EMAIL = os.getenv("SPACETRACK_EMAIL")
PASSWORD = os.getenv("SPACETRACK_PASSWORD")
BASE_URL = "https://www.space-track.org"

# Giriş yap
session = requests.Session()
session.post(f"{BASE_URL}/ajaxauth/login", data={
    "identity": EMAIL,
    "password": PASSWORD
})

# ISS TLE verisini çek
url = f"{BASE_URL}/basicspacedata/query/class/gp/NORAD_CAT_ID/25544/format/tle"
response = session.get(url)
lines = response.text.strip().split("\n")
line1, line2 = lines[0], lines[1]

# SGP4 ile uyduyu tanımla
satellite = Satrec.twoline2rv(line1, line2)

# Şu anki zamanı al
now = datetime.now(timezone.utc)
yr = now.year
mo = now.month
dy = now.day
hr = now.hour
mi = now.minute
se = now.second

# Julian tarihe çevir
jd, fr = jday(yr, mo, dy, hr, mi, se)

# Konum hesapla
error, position, velocity = satellite.sgp4(jd, fr)

if error == 0:
    x, y, z = position  # km cinsinden, Dünya merkezi referanslı

    # ECI → Enlem/Boylam dönüşümü
    import math
    r = math.sqrt(x**2 + y**2 + z**2)
    lat = math.degrees(math.asin(z / r))
    lon = math.degrees(math.atan2(y, x))

    print(f"\n🛸 ISS Şu An Nerede? ({now.strftime('%H:%M:%S')} UTC)")
    print(f"   Enlem  : {lat:.4f}°")
    print(f"   Boylam : {lon:.4f}°")
    print(f"   İrtifa : {r - 6371:.1f} km")
    print(f"\n🗺️  Google Maps'te gör:")
    print(f"   https://www.google.com/maps?q={lat:.4f},{lon:.4f}")
else:
    print(f"❌ Hesaplama hatası: {error}")
