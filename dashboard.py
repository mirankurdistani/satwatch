import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import math
import subprocess
from datetime import datetime

st.set_page_config(page_title="SatWatch", page_icon="🛸", layout="wide")

def mm_to_alt(mm):
    mu = 398600.4418
    n = mm * 2 * math.pi / 86400
    a = (mu / n**2) ** (1/3)
    return round(a - 6371, 1)

def format_pc(pc):
    if not pc or pc <= 0: return "—"
    if pc < 1e-100: return "~0"
    exp = math.floor(math.log10(pc))
    m = pc / (10**exp)
    return f"{m:.1f}×10^{exp}"

@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect("satwatch.db")
    satellites = pd.read_sql("SELECT * FROM satellites", conn)
    change_log = pd.read_sql("""
        SELECT cl.name, cl.norad_id, cl.change_type,
               cl.new_epoch, cl.detected_at, s.mean_motion, s.inclination
        FROM change_log cl
        JOIN satellites s ON cl.norad_id = s.norad_id
        ORDER BY cl.detected_at DESC
    """, conn)
    try:
        conj_log = pd.read_sql("SELECT * FROM conjunction_log ORDER BY scan_time DESC", conn)
    except:
        conj_log = pd.DataFrame()
    stats = {
        "total": pd.read_sql("SELECT COUNT(*) as n FROM satellites", conn)["n"][0],
        "last_update": pd.read_sql("SELECT MAX(updated_at) as t FROM satellites", conn)["t"][0]
    }
    conn.close()
    return satellites, change_log, conj_log, stats

satellites, change_log, conj_log, stats = load_data()
satellites["altitude"] = satellites["mean_motion"].apply(mm_to_alt)
change_log["altitude"] = change_log["mean_motion"].apply(mm_to_alt)
fleet_avg = satellites["mean_motion"].mean()
change_log["anomaly_score"] = ((change_log["mean_motion"] - fleet_avg).abs() * 1000).round(2)
maneuvers = change_log[change_log["change_type"] == "maneuver_candidate"]
deorbiting = maneuvers[maneuvers["altitude"] < 300]

# HEADER
col1, col2 = st.columns([4, 1])
with col1:
    st.markdown("## 🛸 SatWatch — Starlink Manevra İzleme")
    st.caption(f"Son güncelleme: {str(stats['last_update'])[:19]} UTC")
with col2:
    st.write("")
    if st.button("🔄 Pipeline Çalıştır", use_container_width=True):
        with st.spinner("Çalışıyor..."):
            result = subprocess.run(["python", "satwatch_pipeline.py"],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                st.success("✅ Tamamlandı!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Hata oluştu")

st.divider()

# METRİKLER
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Toplam Starlink", f"{stats['total']:,}")
c2.metric("Manevra Adayı", f"{len(maneuvers):,}")
c3.metric("Deorbit (<300km)", f"{len(deorbiting):,}", delta="kritik", delta_color="inverse")
c4.metric("Filo Ort. İrtifası", f"{satellites['altitude'].mean():.0f} km")
c5.metric("Conjunction Kaydı", f"{len(conj_log):,}")

st.divider()

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
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Eğim vs İrtifa")
        fig2 = px.scatter(maneuvers.head(500), x="inclination", y="altitude",
                          color="anomaly_score", color_continuous_scale="RdYlGn_r",
                          hover_name="name",
                          labels={"inclination": "Eğim (°)", "altitude": "İrtifa (km)"})
        fig2.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0),
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

    with right:
        st.subheader("🚨 En Yüksek Anomali")
        top = maneuvers.nlargest(12, "anomaly_score")[["name","altitude","anomaly_score"]].reset_index(drop=True)
        top.columns = ["Uydu","İrtifa (km)","Skor"]
        st.dataframe(top, use_container_width=True, height=240, hide_index=True)

        st.subheader("☄️ Deorbit Adayları")
        deo = deorbiting.nsmallest(8, "altitude")[["name","altitude","anomaly_score"]].reset_index(drop=True)
        deo.columns = ["Uydu","İrtifa (km)","Skor"]
        st.dataframe(deo, use_container_width=True, height=220, hide_index=True)

with tab2:
    st.subheader("Conjunction Log")
    if conj_log.empty:
        st.info("Henüz conjunction kaydı yok.")
    else:
        all_risks = sorted(conj_log["risk_level"].unique().tolist())
        default_risks = [r for r in all_risks if r != "LOW"]
        risk_filter = st.multiselect(
            "Risk seviyesi filtrele",
            options=all_risks,
            default=default_risks
        )
        filtered = conj_log[conj_log["risk_level"].isin(risk_filter)]
        if "pc" in filtered.columns:
            filtered = filtered.copy()
            filtered["Pc"] = filtered["pc"].apply(format_pc)
        st.dataframe(filtered.reset_index(drop=True),
                     use_container_width=True, height=400, hide_index=True)

with tab3:
    st.subheader("Uydu Ara")
    search = st.text_input("Uydu adı", placeholder="STARLINK-1816")
    filtered = maneuvers if not search else maneuvers[
        maneuvers["name"].str.contains(search.upper(), na=False)
    ]
    st.dataframe(
        filtered[["name","altitude","anomaly_score","inclination","new_epoch"]].reset_index(drop=True),
        use_container_width=True, height=400, hide_index=True
    )
