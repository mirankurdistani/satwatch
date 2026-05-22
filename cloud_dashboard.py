import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import math
from datetime import datetime

st.set_page_config(page_title="SatWatch", page_icon="🛸", layout="wide")

def mm_to_alt(mm):
    mu = 398600.4418
    n = mm * 2 * math.pi / 86400
    a = (mu / n**2) ** (1/3)
    return round(a - 6371, 1)

def get_credentials():
    try:
        return st.secrets["SPACETRACK_EMAIL"], st.secrets["SPACETRACK_PASSWORD"]
    except:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv("SPACETRACK_EMAIL"), os.getenv("SPACETRACK_PASSWORD")

@st.cache_data(ttl=3600)
def load_starlink_data():
    EMAIL, PASSWORD = get_credentials()
    BASE_URL = "https://www.space-track.org"
    session = requests.Session()
    session.post(f"{BASE_URL}/ajaxauth/login", data={
        "identity": EMAIL, "password": PASSWORD
    })
    url = (f"{BASE_URL}/basicspacedata/query/class/gp"
           f"/OBJECT_NAME/STARLINK~~/orderby/NORAD_CAT_ID asc/format/json")
    response = session.get(url)
    data = response.json()
    df = pd.DataFrame(data)
    df["mean_motion"] = pd.to_numeric(df["MEAN_MOTION"], errors="coerce")
    df["inclination"] = pd.to_numeric(df["INCLINATION"], errors="coerce")
    df["altitude"] = df["mean_motion"].apply(mm_to_alt)
    df["name"] = df["OBJECT_NAME"]
    return df

# HEADER
st.markdown("## 🛸 SatWatch — Starlink Manevra İzleme")
st.caption(f"Canlı veri: Space-Track.org · {datetime.utcnow().strftime('%H:%M:%S')} UTC")

with st.spinner("Space-Track'ten veri çekiliyor..."):
    df = load_starlink_data()

st.divider()

fleet_avg = df["mean_motion"].mean()
df["anomaly_score"] = ((df["mean_motion"] - fleet_avg).abs() * 1000).round(2)
deorbiting = df[df["altitude"] < 300]
high_anomaly = df[df["anomaly_score"] > 100]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Toplam Starlink", f"{len(df):,}")
c2.metric("Yüksek Anomali", f"{len(high_anomaly):,}")
c3.metric("Deorbit (<300km)", f"{len(deorbiting):,}", delta="kritik", delta_color="inverse")
c4.metric("Filo Ort. İrtifası", f"{df['altitude'].mean():.0f} km")

st.divider()

tab1, tab2 = st.tabs(["📊 Genel Bakış", "🔍 Detay Ara"])

with tab1:
    left, right = st.columns([3, 2])
    with left:
        st.subheader("İrtifa Dağılımı")
        fig = px.histogram(df, x="altitude", nbins=50,
                           color_discrete_sequence=["#185FA5"],
                           labels={"altitude": "İrtifa (km)"})
        fig.add_vline(x=300, line_dash="dash", line_color="#E24B4A",
                      annotation_text="Deorbit sınırı")
        fig.update_layout(height=280, margin=dict(l=0,r=0,t=10,b=0),
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Eğim vs İrtifa")
        fig2 = px.scatter(df.sample(min(500, len(df))),
                          x="inclination", y="altitude",
                          color="anomaly_score",
                          color_continuous_scale="RdYlGn_r",
                          hover_name="name",
                          labels={"inclination": "Eğim (°)", "altitude": "İrtifa (km)"})
        fig2.update_layout(height=280, margin=dict(l=0,r=0,t=10,b=0),
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

    with right:
        st.subheader("🚨 En Yüksek Anomali")
        top = df.nlargest(15, "anomaly_score")[["name","altitude","anomaly_score"]].reset_index(drop=True)
        top.columns = ["Uydu","İrtifa (km)","Skor"]
        st.dataframe(top, use_container_width=True, height=260, hide_index=True)

        st.subheader("☄️ Deorbit Adayları")
        deo = deorbiting.nsmallest(10, "altitude")[["name","altitude","anomaly_score"]].reset_index(drop=True)
        deo.columns = ["Uydu","İrtifa (km)","Skor"]
        st.dataframe(deo, use_container_width=True, height=250, hide_index=True)

with tab2:
    search = st.text_input("Uydu adı ara", placeholder="STARLINK-1816")
    filtered = df if not search else df[df["name"].str.contains(search.upper(), na=False)]
    st.dataframe(
        filtered[["name","altitude","anomaly_score","inclination","EPOCH"]].reset_index(drop=True),
        use_container_width=True, height=400, hide_index=True
    )
