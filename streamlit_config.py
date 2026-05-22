import os
try:
    import streamlit as st
    EMAIL = st.secrets["SPACETRACK_EMAIL"]
    PASSWORD = st.secrets["SPACETRACK_PASSWORD"]
except Exception:
    from dotenv import load_dotenv
    load_dotenv()
    EMAIL = os.getenv("SPACETRACK_EMAIL")
    PASSWORD = os.getenv("SPACETRACK_PASSWORD")
