import requests
import os
import json
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

EMAIL = os.getenv("SPACETRACK_EMAIL")
PASSWORD = os.getenv("SPACETRACK_PASSWORD")
BASE_URL = "https://www.space-track.org"

session = requests.Session()
session.post(f"{BASE_URL}/ajaxauth/login", data={
    "identity": EMAIL,
    "password": PASSWORD
})

print("⏳ Starlink TLE verisi çekiliyor...")

url = (
    f"{BASE_URL}/basicspacedata/query/class/gp"
    f"/OBJECT_NAME/STARLINK~~"
    f"/orderby/NORAD_CAT_ID asc"
    f"/format/json"
)

response = session.get(url)
data = response.json()

print(f"✅ {len(data)} Starlink uydusu bulundu!")
print()

# İlk 5 uyduyu göster
print("İlk 5 uydu:")
for sat in data[:5]:
    print(f"  {sat['OBJECT_NAME']:25} | NORAD: {sat['NORAD_CAT_ID']} | İrtifa: ~{float(sat['MEAN_MOTION']):.4f} tur/gün")

# Dosyaya kaydet
with open("starlink_data.json", "w") as f:
    json.dump(data, f, indent=2)

print(f"\n💾 Tüm veri 'starlink_data.json' dosyasına kaydedildi.")
print(f"📅 Çekilme zamanı: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
