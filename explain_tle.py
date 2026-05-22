import requests
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("SPACETRACK_EMAIL")
PASSWORD = os.getenv("SPACETRACK_PASSWORD")
BASE_URL = "https://www.space-track.org"

session = requests.Session()
session.post(f"{BASE_URL}/ajaxauth/login", data={
    "identity": EMAIL,
    "password": PASSWORD
})

url = f"{BASE_URL}/basicspacedata/query/class/gp/NORAD_CAT_ID/25544/format/tle"
response = session.get(url)
lines = response.text.strip().split("\n")
line1, line2 = lines[0], lines[1]

print("=" * 60)
print("TLE SATIR 1 ANATOMİSİ")
print("=" * 60)
print(f"Ham veri : {line1}")
print()
print(f"  Satır numarası     : {line1[0]}")
print(f"  NORAD ID           : {line1[2:7].strip()} (ISS'in evrensel kimliği)")
print(f"  Sınıflandırma      : {line1[7]} (U = Unclassified)")
print(f"  Fırlatma yılı      : 20{line1[9:11]}")
print(f"  Epoch (gün)        : {line1[20:32].strip()} (yılın kaçıncı günü + kesir)")
print(f"  Sürüklenme (drag)  : {line1[33:43].strip()}")

print()
print("=" * 60)
print("TLE SATIR 2 ANATOMİSİ")
print("=" * 60)
print(f"Ham veri : {line2}")
print()
print(f"  Eğim (inclination) : {line2[8:16].strip()}° (yörünge eğim açısı)")
print(f"  RAAN               : {line2[17:25].strip()}° (düğüm noktası)")
print(f"  Dışmerkezlik       : 0.{line2[26:33].strip()} (daireye ne kadar yakın)")
print(f"  Ortalama hareket   : {line2[52:63].strip()} tur/gün")

# Tur/gün → irtifa hesabı
import math
mean_motion = float(line2[52:63].strip())
mu = 398600.4418  # km³/s²
n = mean_motion * 2 * math.pi / 86400
a = (mu / n**2) ** (1/3)
altitude = a - 6371

print(f"  Hesaplanan irtifa  : {altitude:.1f} km")
print(f"  Hız (yaklaşık)     : {math.sqrt(mu/a):.0f} m/s = {math.sqrt(mu/a)*3.6:.0f} km/h")
print()
print("💡 Bu sayılar değişirse → uydu manevra yapmış demektir.")
print("   SatWatch tam olarak bunu izleyecek.")
