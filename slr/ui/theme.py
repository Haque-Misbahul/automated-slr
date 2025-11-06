# slr/ui/theme.py
import os
import streamlit as st

def inject_css():
    """Load shared CSS for all Streamlit pages."""
    # Load external CSS file if present (edit this file anytime to restyle the app)
    css_path = os.path.join(os.path.dirname(__file__), "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    # You can keep small per-app overrides here if needed
