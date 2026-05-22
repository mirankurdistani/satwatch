import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import math
import subprocess
from datetime import datetime

st.set_page_config(
    page_title="SatWatch",
    page_icon="🛸",
    layout="wide"
)

def mm_to_alt(mm):
    mu = 398600.4418
    n = mm * 2 * math.pi / 86400
    a = (mu / n**2) ** (1/3)
    return round(a - 6371, 1)

@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect("satwatch.db")

    satellites = pd.read_sql("""
        SELECT norad_id, name, mean_motion, inclination,
               eccentricity, raan, updated_at
        FROM satellites
    """, conn)

    change_log = pd.read_sql("""
        SELECT cl.name, cl.norad_id, cl.change_type,
               cl.new_epoch, cl.detected_at, s.mean_motion,
               s.inclination
        FROM change_log cl
        JOIN satellites s ON cl.norad_id = s.norad_id
        ORDER BY cl.detected_at DESC
    """, conn)

    try:
        conjunction_log = pd.read_sql("""
            SELECT sat1_name, sat2_name, min_distance_km,
                   relative_velocity_kms, risk_level,
                   closest_approach_time, scan_time
            FROM conjunction_log
            ORDER BY scan_time DESC
        """, conn)
    except Exception:
        conjunction_log = pd.DataFrame()

    stats = {
        "total": pd.read_sql("SELECT COUNT(*) as n FROM satellites", conn)["n"][0],
        "changes": pd.read_sql("SELECT COUNT(*) as n FROM change_log", conn)["n"][0],
        "last_update": pd.read_sql(
            "SELECT MAX(updated_at) as t FROM satellites", conn
        )["t"][0]
    }

    conn.close()
    return satellites, change_log, conjunction_log, stats

satellites, change_log, conjunction_log, stats = load_data()

satellites["altitude"] = satellites["mean_motion"].apply(mm_to_alt)
change_log["altitude"] = change_log["mean_motion"].apply(mm_to_alt)

fleet_avg_mm = satellites["mean_motion"].mean()
change_log["anomaly_score"] = (
    (change_log["mean_motion"] - fleet_avg_mm).abs() * 1000
).round(2)

maneuvers = change_log[change_log["change_type"] == "maneuver_candidate"]
deorbiting = maneuvers[maneuvers["altitude"] < 300]

# ── HEADER ──
col_title, col_btn = st.columns([4, 1])
with col_title:
    st.markdown("## 🛸 SatWatch — Starlink Manevra İzleme")
    st.caption(f"Son güncelleme: {str(stats['last_update'])[:19]} UTC")
with col_btn:
    st.write("")
    if st.button("🔄 Pipeline Çalıştır", use_container_width=True):
        with st.spinner("Pipeline çalışıyor..."):
            result = subprocess.run(
                ["python", "satwatch_pipeline.py"],
                capture_output=True, text=True, cwd="."
            )
            if result.returncode == 0:
                st.success("✅ Tamamlandı!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(f"Hata: {result.stderr[-300:]}")

st.divider()

# ── METRİKLER ──
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Toplam Starlink", f"{stats['total']:,}")
m2.metric("Manevra Adayı", f"{len(maneuvers):,}")
m3.metric("Deorbit (<300km)", f"{len(deorbiting):,}",
          delta="kritik", delta_color="inverse")
m4.metric("Filo Ort. İrtifası", f"{satellites['altitude'].mean():.0f} km")
m5.metric("Conjunction Kaydı", f"{len(conjunction_log):,}")

st.divider()

# ── SEKMELER ──
tab1, tab2, tab3 = st.tabs(["📊 Genel Bakış", "⚠️ Conjunction Log", "🔍 Detay Ara"])

with tab1:
    left, right = st.columns([3, 2])

    with left:
        st.subheader("İrtifa Dağılımı")
        fig = px.histogram(maneuvers, x="altitude", nbins=40,
                           color_discrete_sequence=["#185FA5"],
                           labels={"altitude": "İrtifa (km)"})
        fig.add_vline(x=300, line_dash="dash", line_color="#E24B4A",
                      annotation_text="Deorbit sınırı")
        fig.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0),
                          plot_bgcolor="rgba(0,0,0,0)",
                          paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Eğim vs İrtifa")
        fig2 = px.scatter(maneuvers.head(500), x="inclination",
                          y="altitude", color="anomaly_score",
                          color_continuous_scale="RdYlGn_r",
                          hover_name="name",
                          labels={"inclination": "Eğim (°)",
                                  "altitude": "İrtifa (km)",
                                  "anomaly_score": "Anomali"})
        fig2.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0),
                           plot_bgcolor="rgba(0,0,0,0)",
                           paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

    with right:
        st.subheader("🚨 En Yüksek Anomali")
        top = maneuvers.nlargest(12, "anomaly_score")[
            ["name", "altitude", "anomaly_score"]
        ].reset_index(drop=True)
        top.columns = ["Uydu", "İrtifa (km)", "Skor"]
        st.dataframe(top, use_container_width=True,
                     height=240, hide_index=True)

        st.subheader("☄️ Deorbit Adayları")
        deo = deorbiting.nsmallest(8, "altitude")[
            ["name", "altitude", "anomaly_score"]
        ].reset_index(drop=True)
        deo.columns = ["Uydu", "İrtifa (km)", "Skor"]
        st.dataframe(deo, use_container_width=True,
                     height=220, hide_index=True)

with tab2:
    st.subheader("Conjunction Log")
    if conjunction_log.empty:
        st.info("Henüz conjunction kaydı yok — pipeline çalıştırınca dolacak.")
    else:
        risk_filter = st.multiselect(
            "Risk seviyesi filtrele",
            ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
            default=["CRITICAL", "HIGH", "MEDIUM"]
        )
        filtered_conj = conjunction_log[
            conjunction_log["risk_level"].isin(risk_filter)
        ]
        st.dataframe(
            filtered_conj.reset_index(drop=True),
            use_container_width=True,
            height=400,
            column_config={
                "min_distance_km": st.column_config.NumberColumn(
                    "Mesafe (km)", format="%.3f"
                ),
                "relative_velocity_kms": st.column_config.NumberColumn(
                    "Hız (km/s)", format="%.3f"
                ),
                "risk_level": "Risk"
            },
            hide_index=True
        )

with tab3:
    st.subheader("Uydu Ara")
    search = st.text_input("Uydu adı", placeholder="STARLINK-1816")
    filtered = maneuvers if not search else maneuvers[
        maneuvers["name"].str.contains(search.upper(), na=False)
    ]
    st.dataframe(
        filtered[["name", "altitude", "anomaly_score",
                  "inclination", "new_epoch"]].reset_index(drop=True),
        use_container_width=True,
        height=400,
        column_config={
            "name": "Uydu",
            "altitude": st.column_config.NumberColumn("İrtifa (km)", format="%.1f"),
            "anomaly_score": st.column_config.ProgressColumn(
                "Anomali Skoru", min_value=0, max_value=1000
            ),
            "inclination": st.column_config.NumberColumn("Eğim (°)", format="%.2f"),
            "new_epoch": "Epoch"
        },
        hide_index=True
    )
