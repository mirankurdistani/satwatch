import requests
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("SPACETRACK_EMAIL")
PASSWORD = os.getenv("SPACETRACK_PASSWORD")
BASE_URL = "https://www.space-track.org"

session = requests.Session()

# Giriş yap
login = session.post(f"{BASE_URL}/ajaxauth/login", data={
    "identity": EMAIL,
    "password": PASSWORD
})

if login.status_code == 200:
    print("✅ Space-Track'e başarıyla giriş yapıldı!")
else:
    print(f"❌ Giriş başarısız: {login.status_code}")
    exit()

# ISS'in TLE verisini çek (NORAD ID: 25544)
url = f"{BASE_URL}/basicspacedata/query/class/gp/NORAD_CAT_ID/25544/format/tle"
response = session.get(url)

print("\n🛸 ISS (Uluslararası Uzay İstasyonu) TLE verisi:")
print(response.text)
