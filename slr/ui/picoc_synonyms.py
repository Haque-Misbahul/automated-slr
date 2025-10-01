import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import json, hashlib
import streamlit as st
from slr.agents.agent import run_define_picoc
from slr.query.builder import build_boolean_query
from slr.query.adapters.arxiv import build_arxiv_query, arxiv_api_url

# ---------------- Page setup ----------------
st.set_page_config(page_title="Planning → PICOC & Query (arXiv)", layout="wide")

def inject_css():
    # Support both style.css and styles.css
    for css_name in ("styles.css", "style.css"):
        css_path = os.path.join(os.path.dirname(__file__), css_name)
        if os.path.exists(css_path):
            with open(css_path, "r", encoding="utf-8") as f:
                st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
            return
    # Fallback inline CSS
    st.markdown("""
    <style>
      .block-container {padding-top: 0.8rem; padding-bottom: 0.8rem;}
      section[data-testid="stSidebar"] {padding-top: 0.5rem;}
      div[data-testid="stVerticalBlock"] {gap: 0.4rem !important;}
      label[data-baseweb="checkbox"] {font-size: 0.92rem;}
      h1, h2, h3 {margin-bottom: 0.4rem;}
    </style>
    """, unsafe_allow_html=True)

inject_css()

st.markdown(
    "<h2 style='margin-top:25px;'>🧩 Planning • Step 1: Define PICOC & Synonyms (AI)</h2>",
    unsafe_allow_html=True,
)

# ---------------- Inputs ----------------
topic = st.text_input(
    "Topic / initial idea",
    value=st.session_state.get("topic", ""),
    placeholder="e.g., LLM-based code review automation in software engineering",
)

# ---------------- Generate PICOC + synonyms ----------------
if st.button("Generate PICOC & Synonyms (AI)", use_container_width=True):
    seed = topic.strip()
    if not seed:
        st.warning("Please enter a topic/keyword first.")
        st.stop()
    with st.spinner("Calling LLM (gpt-oss-120b) to define PICOC and facet synonyms..."):
        try:
            data = run_define_picoc(seed)  # {"picoc": {...}, "synonyms": {...}}
        except Exception as e:
            st.error(f"LLM call failed: {e}")
            st.stop()
    # persist results for reruns
    st.session_state["topic"] = seed
    st.session_state["ai_picoc"] = data.get("picoc", {})
    st.session_state["ai_syns"] = data.get("synonyms", {})
    st.session_state["selected_synonyms"] = {}   # reset selections
    st.session_state["show_query"] = False       # hide query section until user clicks

# ---------------- Render selections if we have data ----------------
ai_picoc = st.session_state.get("ai_picoc")
ai_syns  = st.session_state.get("ai_syns")

if ai_picoc and ai_syns:
    # PICOC preview
    st.subheader("PICOC")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Population:** {ai_picoc.get('population','')}")
        st.write(f"**Intervention:** {ai_picoc.get('intervention','')}")
        st.write(f"**Comparison:** {ai_picoc.get('comparison','')}")
    with col2:
        st.write(f"**Outcome:** {ai_picoc.get('outcome','')}")
        st.write(f"**Context:** {ai_picoc.get('context','')}")

    # helper for stable widget keys per topic
    def topic_key_suffix(txt: str) -> str:
        return hashlib.sha1(txt.encode("utf-8")).hexdigest()[:8]
    key_suffix = topic_key_suffix(st.session_state.get("topic", ""))

    # Synonyms with checkboxes
    st.subheader("Facet-wise synonyms (select what to keep)")
    prev_sel = st.session_state.get("selected_synonyms", {})

    def checklist(facet: str, items: list[str]) -> list[str]:
        if not items:
            return []
        cols = st.columns(4)
        selected = []
        prev = set(prev_sel.get(facet, []))
        for i, term in enumerate(items):
            col = cols[i % 4]
            default_checked = True if not prev else (term in prev)
            key = f"chk_{facet}_{i}_{key_suffix}"
            with col:
                keep = st.checkbox(term, key=key, value=default_checked)
            if keep:
                selected.append(term)
        return selected

    selected_synonyms = {}
    for facet in ("Population", "Intervention", "Comparison", "Outcome", "Context"):
        items = ai_syns.get(facet, [])
        with st.expander(f"{facet} ({len(items)} terms)", expanded=True):
            selected_synonyms[facet] = checklist(facet, items)

    st.session_state["selected_synonyms"] = selected_synonyms

    st.markdown("---")
    st.write("**Selected counts:**", {k: len(v) for k, v in selected_synonyms.items()})

# ---------------- Build Query (in-page) ----------------
st.markdown(
    "<h2 style='margin-top:10px;'>🔎 Step 2: Build Boolean Query for arXiv</h2>",
    unsafe_allow_html=True,
)

# Guard: don't render builder until we have AI outputs + selections
if not st.session_state.get("ai_syns"):
    st.info("Generate PICOC & synonyms first (Step 1).")
    st.stop()

# Use the latest selections (from the checkboxes above)
selected_synonyms = st.session_state.get("selected_synonyms", {})

# Choose which facets to include (too many facets → 0 results)
all_facets = ["Population", "Intervention", "Comparison", "Outcome", "Context"]
include_facets = st.multiselect(
    "Include facets",
    options=all_facets,
    default=["Intervention", "Population"],   # good starting point
    help="Start narrow with Intervention, then add Population. Outcome/Context often over-constrain arXiv."
)

# SAFELY build the dict used for the query
selected_for_query = {f: selected_synonyms.get(f, []) for f in include_facets}

# If nothing is selected for the chosen facets, stop early
if not any(selected_for_query.values()):
    st.warning("No terms selected for the chosen facets. Check some boxes above or pick different facets.")
    st.stop()

# -------- Target fields (arXiv) --------
st.subheader("Target fields (arXiv)")
c1, c2, c3 = st.columns(3)
with c1:
    f_ti  = st.checkbox("Title (ti)", value=True, key="fld_ti")
with c2:
    f_abs = st.checkbox("Abstract (abs)", value=True, key="fld_abs")
with c3:
    f_all = st.checkbox("All fields (all)", value=False, key="fld_all")

fields = []
if f_ti:  fields.append("ti")
if f_abs: fields.append("abs")
if f_all: fields.append("all")
if not fields:
    st.warning("Select at least one field.")
    st.stop()

# -------- Build queries using ONLY the selected facets --------
from slr.query.builder import build_boolean_query
from slr.query.adapters.arxiv import build_arxiv_query, arxiv_api_url

generic_query, parts = build_boolean_query(selected_for_query)
arxiv_query = build_arxiv_query(parts, fields=fields)
api_url     = arxiv_api_url(arxiv_query, start=0, max_results=50)

st.subheader("Generic Boolean (neutral)")
st.code(generic_query or "(empty)")

st.subheader("arXiv search_query")
st.code(arxiv_query or "(empty)")

st.markdown(f"**API URL (copy to browser or script):**  \n[{api_url}]({api_url})")

# ---- Preview results from arXiv ----
st.markdown("### Preview results")
pc1, pc2, pc3 = st.columns(3)
with pc1:
    max_results = st.number_input("How many?", min_value=5, max_value=100, value=10, step=5, key="pv_max")
with pc2:
    start_idx   = st.number_input("Start index", min_value=0, max_value=1000, value=0, step=10, key="pv_start")
with pc3:
    sort_by     = st.selectbox("Sort by", ["relevance", "lastUpdatedDate", "submittedDate"], index=0, key="pv_sort")

if st.button("Fetch preview", use_container_width=True):
    from slr.query.arxiv_api import build_url, fetch
    with st.spinner("Fetching from arXiv..."):
        preview_url = build_url(arxiv_query, start=start_idx, max_results=int(max_results), sort_by=sort_by)
        try:
            rows = fetch(arxiv_query, start=start_idx, max_results=int(max_results))
        except Exception as e:
            st.error(f"arXiv fetch failed: {e}")
            rows = []
    st.caption(f"API call: {preview_url}")
    if not rows:
        st.info("No results.")
    else:
        for i, r in enumerate(rows, start=1):
            st.markdown(f"**{i}. [{r['title']}]({r['link']})**")
            st.write(f"_Published:_ {r['published']}  |  _Category:_ `{r['category']}`")
            st.write(", ".join(r["authors"]))
            with st.expander("Abstract", expanded=False):
                st.write(r["summary"])
            st.markdown("---")

# ---- Download bundle (for later conducting phase) ----
bundle = {
    "topic": st.session_state.get("topic", ""),
    "picoc": ai_picoc,
    "selected_synonyms": selected_for_query,   # <- only facets you included
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
