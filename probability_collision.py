import math
import sqlite3
from sgp4.api import Satrec, jday
from datetime import datetime, timezone, timedelta

def get_position(sat, dt):
    jd, fr = jday(dt.year, dt.month, dt.day,
                  dt.hour, dt.minute, dt.second)
    err, pos, vel = sat.sgp4(jd, fr)
    return (pos, vel) if err == 0 else (None, None)

def distance_km(p1, p2):
    return math.sqrt(sum((a-b)**2 for a, b in zip(p1, p2)))

def rel_velocity(v1, v2):
    return math.sqrt(sum((a-b)**2 for a, b in zip(v1, v2)))

def probability_of_collision(miss_distance_km, rel_vel_kms,
                              combined_radius_m=10):
    """
    Basitleştirilmiş Pc hesabı — Chan metoduna dayalı.
    
    miss_distance_km : En yakın geçiş mesafesi (km)
    rel_vel_kms      : Görece hız (km/s)
    combined_radius  : İki uydunun toplam yarıçapı (metre)
                       Starlink için ~5m + ~5m = 10m varsayılan
    
    Gerçek Pc hesabı covariance matrisi gerektirir.
    Bu implementasyon pozisyon belirsizliğini 
    sabit sigma ile modellemektedir.
    """
    # Pozisyon belirsizliği (sigma) — TLE için tipik değer
    # Gerçekte covariance'tan gelir, biz sabit kullanıyoruz
    sigma_r = 0.2   # km — radyal belirsizlik
    sigma_t = 1.0   # km — tanjantiyel belirsizlik
    sigma_n = 0.2   # km — normal belirsizlik
    
    # Birleşik belirsizlik
    sigma_combined = math.sqrt(sigma_r**2 + sigma_t**2 + sigma_n**2)
    
    # Çarpışma tüpü yarıçapı (km)
    r_combined = combined_radius_m / 1000.0
    
    # Gaussian yaklaşımı ile Pc
    # Pc ≈ (π * r²) / (2π * σ²) * exp(-d²/2σ²)
    d = miss_distance_km
    sigma2 = sigma_combined ** 2
    
    if d == 0:
        return 1.0
    
    pc = (r_combined**2 / (2 * sigma2)) * math.exp(-d**2 / (2 * sigma2))
    
    # Görece hız faktörü — yüksek hız = daha kısa interaction time
    # Düşük hız = daha uzun süre yakın = daha yüksek risk
    vel_factor = max(0.1, min(1.0, 7.5 / rel_vel_kms)) if rel_vel_kms > 0 else 1.0
    pc_adjusted = pc * vel_factor
    
    return min(pc_adjusted, 1.0)

def pc_risk_level(pc):
    if pc >= 1e-4:   return "🔴 KRİTİK"
    if pc >= 1e-5:   return "🟠 YÜKSEK"
    if pc >= 1e-6:   return "🟡 ORTA"
    return "🟢 DÜŞÜK"

def find_close_approaches(sats, hours=24, step=60, dist_threshold=200):
    """Belirli mesafe altındaki tüm geçişleri bul"""
    now = datetime.now(timezone.utc)
    results = []
    
    for i in range(len(sats)):
        for j in range(i+1, len(sats)):
            s1, s2 = sats[i], sats[j]
            try:
                sat1 = Satrec.twoline2rv(s1[2], s1[3])
                sat2 = Satrec.twoline2rv(s2[2], s2[3])
                min_dist = float("inf")
                min_time = None
                min_vel = None
                t = now
                while t < now + timedelta(hours=hours):
                    p1, v1 = get_position(sat1, t)
                    p2, v2 = get_position(sat2, t)
                    if p1 and p2:
                        d = distance_km(p1, p2)
                        if d < min_dist:
                            min_dist = d
                            min_time = t
                            min_vel = rel_velocity(v1, v2)
                    t += timedelta(seconds=step)
                
                if min_dist < dist_threshold:
                    pc = probability_of_collision(min_dist, min_vel or 7.5)
                    results.append({
                        "sat1": s1[1], "sat2": s2[1],
                        "dist": round(min_dist, 3),
                        "vel": round(min_vel, 3) if min_vel else 0,
                        "pc": pc,
                        "time": min_time
                    })
            except Exception:
                pass
    
    return sorted(results, key=lambda x: x["pc"], reverse=True)

def load_satellites(limit=40):
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT norad_id, name, tle_line1, tle_line2
        FROM satellites
        WHERE tle_line1 IS NOT NULL
          AND tle_line2 IS NOT NULL
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

def format_pc(pc):
    if pc == 0:
        return "0"
    exp = math.floor(math.log10(pc))
    mantissa = pc / (10**exp)
    return f"{mantissa:.2f}×10^{exp}"

if __name__ == "__main__":
    print("🛸 SatWatch — Probability of Collision Hesaplayıcı")
    print("   NASA CARA metodolojisine dayalı basitleştirilmiş Pc\n")
    
    sats = load_satellites(limit=40)
    total_pairs = (len(sats) * (len(sats)-1)) // 2
    print(f"✅ {len(sats)} uydu yüklendi ({total_pairs} çift)\n")
    
    print("🔍 <200 km yakın geçişler aranıyor...\n")
    results = find_close_approaches(sats, hours=24, step=60, dist_threshold=200)
    
    if not results:
        print("ℹ️  Bu örnekte 200 km altı yakın geçiş tespit edilmedi.")
        print("   Tüm uydular güvenli mesafede.\n")
        
        # Demo: farklı mesafeler için Pc göster
        print("📊 REFERANS — Farklı mesafelerde Pc değerleri:")
        print(f"   {'Mesafe':>10}  {'Hız':>8}  {'Pc':>15}  Risk")
        print(f"   {'-'*10}  {'-'*8}  {'-'*15}  {'-'*12}")
        
        test_cases = [
            (0.1, 7.5),   # 100m, yüksek hız
            (0.5, 7.5),   # 500m, yüksek hız
            (1.0, 7.5),   # 1km, yüksek hız
            (5.0, 7.5),   # 5km, yüksek hız
            (0.5, 0.5),   # 500m, düşük hız (daha tehlikeli)
            (1.0, 0.1),   # 1km, çok düşük hız
            (10.0, 7.5),  # 10km
            (50.0, 7.5),  # 50km
        ]
        
        for dist, vel in test_cases:
            pc = probability_of_collision(dist, vel)
            print(f"   {dist:>8.1f}km  {vel:>6.1f}km/s  "
                  f"{format_pc(pc):>15}  {pc_risk_level(pc)}")
    else:
        print(f"✅ {len(results)} yakın geçiş bulundu\n")
        print(f"{'='*65}")
        print("EN RİSKLİ GEÇİŞLER — Pc'ye göre sıralı")
        print(f"{'='*65}")
        
        for r in results[:15]:
            t_str = r["time"].strftime("%m-%d %H:%M UTC") if r["time"] else "?"
            print(f"\n  {r['sat1']} ↔ {r['sat2']}")
            print(f"  Mesafe : {r['dist']:.3f} km")
            print(f"  Hız    : {r['vel']:.2f} km/s")
            print(f"  Pc     : {format_pc(r['pc'])}")
            print(f"  Risk   : {pc_risk_level(r['pc'])}")
            print(f"  Zaman  : {t_str}")
