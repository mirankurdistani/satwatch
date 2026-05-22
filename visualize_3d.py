import sqlite3
import math
import plotly.graph_objects as go
from sgp4.api import Satrec, jday
from datetime import datetime, timezone

def get_position(sat, dt):
    jd, fr = jday(dt.year, dt.month, dt.day,
                  dt.hour, dt.minute, dt.second)
    err, pos, vel = sat.sgp4(jd, fr)
    return pos if err == 0 else None

def eci_to_latlon(pos, dt):
    """ECI koordinatlarını enlem/boylam/irtifaya çevir"""
    x, y, z = pos
    r = math.sqrt(x**2 + y**2 + z**2)
    lat = math.degrees(math.asin(z / r))
    
    # Greenwich saat açısı (basitleştirilmiş)
    j2000 = 2451545.0
    jd, fr = jday(dt.year, dt.month, dt.day,
                  dt.hour, dt.minute, dt.second)
    t = (jd + fr - j2000) / 36525.0
    gst = 280.46061837 + 360.98564736629 * (jd + fr - j2000)
    gst = gst % 360
    
    lon = (math.degrees(math.atan2(y, x)) - gst) % 360
    if lon > 180:
        lon -= 360
    
    alt = r - 6371
    return lat, lon, alt

def load_satellites(limit=200):
    conn = sqlite3.connect("satwatch.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT s.norad_id, s.name, s.tle_line1, s.tle_line2,
               s.mean_motion, s.inclination,
               CASE WHEN cl.norad_id IS NOT NULL THEN 1 ELSE 0 END as is_maneuver
        FROM satellites s
        LEFT JOIN (
            SELECT DISTINCT norad_id FROM change_log
            WHERE change_type = 'maneuver_candidate'
        ) cl ON s.norad_id = cl.norad_id
        WHERE s.tle_line1 IS NOT NULL
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

def build_3d_globe(limit=200):
    print(f"🌍 3D Globe oluşturuluyor ({limit} uydu)...")
    now = datetime.now(timezone.utc)
    sats = load_satellites(limit)
    
    normal_lats, normal_lons, normal_alts, normal_names = [], [], [], []
    maneuver_lats, maneuver_lons, maneuver_alts, maneuver_names = [], [], [], []
    deorbit_lats, deorbit_lons, deorbit_alts, deorbit_names = [], [], [], []
    
    for row in sats:
        norad, name, tle1, tle2, mm, inc, is_maneuver = row
        try:
            sat = Satrec.twoline2rv(tle1, tle2)
            pos = get_position(sat, now)
            if not pos:
                continue
            lat, lon, alt = eci_to_latlon(pos, now)
            
            if alt < 300:
                deorbit_lats.append(lat)
                deorbit_lons.append(lon)
                deorbit_alts.append(alt)
                deorbit_names.append(f"{name}<br>İrtifa: {alt:.1f} km<br>⚠️ DEORBİT")
            elif is_maneuver:
                maneuver_lats.append(lat)
                maneuver_lons.append(lon)
                maneuver_alts.append(alt)
                maneuver_names.append(f"{name}<br>İrtifa: {alt:.1f} km<br>🚀 Manevra")
            else:
                normal_lats.append(lat)
                normal_lons.append(lon)
                normal_alts.append(alt)
                normal_names.append(f"{name}<br>İrtifa: {alt:.1f} km")
        except Exception:
            pass
    
    fig = go.Figure()
    
    # Normal uydular
    fig.add_trace(go.Scattergeo(
        lat=normal_lats, lon=normal_lons,
        mode="markers",
        marker=dict(size=4, color="#185FA5", opacity=0.7),
        text=normal_names,
        hoverinfo="text",
        name=f"Normal ({len(normal_lats)})"
    ))
    
    # Manevra yapanlar
    fig.add_trace(go.Scattergeo(
        lat=maneuver_lats, lon=maneuver_lons,
        mode="markers",
        marker=dict(size=6, color="#BA7517", opacity=0.9,
                    symbol="diamond"),
        text=maneuver_names,
        hoverinfo="text",
        name=f"Manevra ({len(maneuver_lats)})"
    ))
    
    # Deorbit adayları
    fig.add_trace(go.Scattergeo(
        lat=deorbit_lats, lon=deorbit_lons,
        mode="markers",
        marker=dict(size=8, color="#E24B4A", opacity=1.0,
                    symbol="x"),
        text=deorbit_names,
        hoverinfo="text",
        name=f"Deorbit ({len(deorbit_lats)})"
    ))
    
    fig.update_layout(
        title=dict(
            text=f"🛸 SatWatch — Starlink Konumları ({now.strftime('%H:%M:%S')} UTC)",
            font=dict(size=16)
        ),
        geo=dict(
            showframe=False,
            showcoastlines=True,
            coastlinecolor="rgba(100,100,100,0.5)",
            showland=True,
            landcolor="rgba(30,40,50,1)",
            showocean=True,
            oceancolor="rgba(10,20,40,1)",
            showlakes=False,
            showcountries=True,
            countrycolor="rgba(80,80,80,0.3)",
            projection_type="orthographic",
            bgcolor="rgba(0,0,0,0)"
        ),
        paper_bgcolor="rgba(15,20,30,1)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            font=dict(color="white"),
            bgcolor="rgba(0,0,0,0.5)"
        ),
        height=700
    )
    
    output = "satwatch_globe.html"
    fig.write_html(output)
    print(f"✅ {len(normal_lats)+len(maneuver_lats)+len(deorbit_lats)} uydu işlendi")
    print(f"   🔵 Normal    : {len(normal_lats)}")
    print(f"   🟡 Manevra   : {len(maneuver_lats)}")
    print(f"   🔴 Deorbit   : {len(deorbit_lats)}")
    print(f"\n💾 Kaydedildi: {output}")
    print("🌍 Açmak için: open satwatch_globe.html")
    return fig

if __name__ == "__main__":
    fig = build_3d_globe(limit=300)
    import subprocess
    subprocess.run(["open", "satwatch_globe.html"])
