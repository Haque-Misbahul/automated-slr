import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import json
import streamlit as st
from slr.query.builder import build_boolean_query
from slr.query.adapters.arxiv import build_arxiv_query, arxiv_api_url

st.set_page_config(page_title="Planning → Step 2: Query Builder (arXiv)", layout="wide")

st.markdown(
    "<h2 style='margin-top:25px;'>🔎 Planning • Step 2: Build Boolean Query for arXiv</h2>",
    unsafe_allow_html=True,
)

# pull curated selections from step 1
selected = st.session_state.get("selected_synonyms", {})
picoc = st.session_state.get("ai_picoc", {})
topic = st.session_state.get("topic", "")

if not selected:
    st.info("No curated terms found. Go back to **Step 1** and select synonyms first.")
    st.stop()

# choose fields to search in arXiv
st.subheader("Target fields (arXiv)")
col1, col2, col3 = st.columns(3)
with col1:
    f_ti = st.checkbox("Title (ti)", value=True)
with col2:
    f_abs = st.checkbox("Abstract (abs)", value=True)
with col3:
    f_all = st.checkbox("All fields (all)", value=False)

fields = []
if f_ti:  fields.append("ti")
if f_abs: fields.append("abs")
if f_all: fields.append("all")  # arXiv supports 'all' as a catch-all field

if not fields:
    st.warning("Select at least one field.")
    st.stop()

# Build generic boolean and arXiv query
generic_query, parts = build_boolean_query(selected)
arxiv_query = build_arxiv_query(parts, fields=fields)
api_url = arxiv_api_url(arxiv_query, start=0, max_results=50)

st.subheader("Generic Boolean (neutral)")
st.code(generic_query or "(empty)")

st.subheader("arXiv search_query")
st.code(arxiv_query or "(empty)")

st.markdown(f"**API URL (copy to browser or script):**  \n[{api_url}]({api_url})")

# download bundle for conduction phase
bundle = {
    "topic": topic,
    "picoc": picoc,
    "selected_synonyms": selected,
    "parts_by_facet": parts,
    "generic_boolean": generic_query,
    "arxiv": {
        "fields": fields,
        "search_query": arxiv_query,
        "api_url": api_url,
        "start": 0,
        "max_results": 50,
    },
}

st.download_button(
    "Download query bundle (JSON)",
    data=json.dumps(bundle, ensure_ascii=False, indent=2),
    file_name="arxiv_query_bundle.json",
    mime="application/json",
    use_container_width=True,
)
