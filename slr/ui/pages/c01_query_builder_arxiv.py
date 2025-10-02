# slr/ui/pages/c01_query_builder_arxiv.py
import sys, os, json, io, csv, math, time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import streamlit as st
from slr.query.builder import build_boolean_query
from slr.query.adapters.arxiv import build_arxiv_query, arxiv_api_url

st.set_page_config(page_title="Conducting → Build & Gather (arXiv)", layout="wide")

# compact layout
st.markdown("""
<style>
div[data-testid="stHorizontalBlock"] > div { padding-right:.35rem !important; }
div[data-baseweb="input"] input { padding-top:6px; padding-bottom:6px; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h2 style='margin-top:25px;'>🔎 Conducting • Build Boolean Query & Gather Studies (arXiv)</h2>", unsafe_allow_html=True)

# ---- Pull curated data from Planning Step 1 ----
topic    = st.session_state.get("topic", "")
ai_picoc = st.session_state.get("ai_picoc")
ai_syns  = st.session_state.get("ai_syns")
selected_synonyms = st.session_state.get("selected_synonyms", {})

if topic:
    st.caption(f"From planning: **{topic}**")

if not ai_syns or not selected_synonyms:
    st.warning("No curated synonyms in session. Go to **Planning → Step 1** and curate facet synonyms first.")
    st.stop()

# ---- Facets to include ----
st.subheader("Facet selection")
all_facets = ["Population", "Intervention", "Comparison", "Outcome", "Context"]
include_facets = st.multiselect(
    "Include facets",
    options=all_facets,
    default=["Intervention", "Population"],
    help="Start narrow (Intervention) and add Population. Outcome/Context often over-constrain arXiv."
)
selected_for_query = {f: selected_synonyms.get(f, []) for f in include_facets}
if not any(selected_for_query.values()):
    st.warning("Selected facets have no terms. Check your selections in Planning Step 1.")
    st.stop()

# ---- Target fields in arXiv ----
st.subheader("Target fields (arXiv)")
c1, c2, c3 = st.columns(3)
with c1: f_ti  = st.checkbox("Title (ti)",     value=True,  key="fld_ti")
with c2: f_abs = st.checkbox("Abstract (abs)", value=True,  key="fld_abs")
with c3: f_all = st.checkbox("All fields (all)", value=False, key="fld_all")

fields = []
if f_ti:  fields.append("ti")
if f_abs: fields.append("abs")
if f_all: fields.append("all")
if not fields:
    st.warning("Select at least one field.")
    st.stop()

# ---- Build Boolean + arXiv search_query ----
generic_query, parts = build_boolean_query(selected_for_query)
arxiv_query = build_arxiv_query(parts, fields=fields)
api_url     = arxiv_api_url(arxiv_query, start=0, max_results=50)

st.subheader("Generic Boolean (neutral)")
st.code(generic_query or "(empty)")

st.subheader("arXiv search_query")
st.code(arxiv_query or "(empty)")

st.markdown(f"**API URL (example):**  \n[{api_url}]({api_url})")

# ---- Preview (quick single-page fetch) ----
st.markdown("### Preview results (single page)")
pc1, pc2, pc3 = st.columns(3)
with pc1:
    pv_max = st.number_input("How many?", min_value=5, max_value=100, value=10, step=5, key="pv_max")
with pc2:
    pv_start = st.number_input("Start index", min_value=0, max_value=10000, value=0, step=10, key="pv_start")
with pc3:
    pv_sort  = st.selectbox("Sort by", ["relevance", "lastUpdatedDate", "submittedDate"], index=0, key="pv_sort")

if st.button("Fetch preview", use_container_width=True):
    from slr.query.arxiv_api import build_url, fetch
    with st.spinner("Fetching from arXiv..."):
        preview_url = build_url(arxiv_query, start=pv_start, max_results=int(pv_max), sort_by=pv_sort)
        try:
            rows = fetch(arxiv_query, start=pv_start, max_results=int(pv_max))
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

# ======================================================================
#                       G A T H E R   S T U D I E S
# ======================================================================
st.markdown("## 📥 Gather studies (all pages)")

g1, g2, g3 = st.columns(3)
with g1:
    page_size = st.number_input("Page size (per API call)", min_value=10, max_value=200, value=100, step=10, help="arXiv supports up to 30000 total; 100 is a good batch size.")
with g2:
    total_cap = st.number_input("Total cap (max records)", min_value=50, max_value=5000, value=1000, step=50, help="Safety cap to avoid huge downloads.")
with g3:
    sleep_ms = st.number_input("Politeness delay (ms)", min_value=0, max_value=2000, value=200, step=50, help="Optional small delay between API calls.")

st.caption("Click to fetch all pages up to the chosen cap. Then download CSV/JSON of the raw entries.")

def _rows_to_csv(rows):
    """Return CSV string from arXiv rows."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id", "title", "summary", "published", "updated", "authors", "category", "link"])
    for r in rows:
        authors = ", ".join(r.get("authors", []))
        w.writerow([
            r.get("id",""),
            r.get("title","").replace("\n"," ").strip(),
            r.get("summary","").replace("\n"," ").strip(),
            r.get("published",""),
            r.get("updated",""),
            authors,
            r.get("category",""),
            r.get("link","")
        ])
    return out.getvalue()

if st.button("🚀 Fetch ALL & prepare downloads", use_container_width=True):
    from slr.query.arxiv_api import fetch  # uses our existing util
    all_rows = []
    total = 0
    batches = math.ceil(total_cap / page_size)
    prog = st.progress(0, text="Starting…")

    for b in range(batches):
        start = b * page_size
        if start >= total_cap:
            break
        with st.spinner(f"Fetching records {start} … {start + page_size - 1}"):
            try:
                rows = fetch(arxiv_query, start=start, max_results=int(page_size))
            except Exception as e:
                st.error(f"Fetch error on batch {b}: {e}")
                break

        if not rows:
            # we likely reached the end
            break

        all_rows.extend(rows)
        total += len(rows)
        prog.progress(min(1.0, total / total_cap), text=f"Fetched {total} records")
        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)

        # stop if fetched less than a full page (end)
        if len(rows) < page_size:
            break

    prog.progress(1.0, text=f"Done. Total collected: {total}")

    if not all_rows:
        st.warning("No records collected.")
    else:
        # Keep in session for the next steps
        st.session_state["gathered_rows"] = all_rows

        # Prepare CSV & JSON blobs for download
        csv_blob = _rows_to_csv(all_rows)
        json_blob = json.dumps(all_rows, ensure_ascii=False, indent=2)

        st.success(f"Collected {len(all_rows)} records. You can download them below.")
        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "⬇️ Download CSV (raw studies)",
                data=csv_blob,
                file_name="arxiv_raw_studies.csv",
                mime="text/csv",
                use_container_width=True
            )
        with d2:
            st.download_button(
                "⬇️ Download JSON (raw studies)",
                data=json_blob,
                file_name="arxiv_raw_studies.json",
                mime="application/json",
                use_container_width=True
            )

# ---- Export the query bundle as before ----
bundle = {
    "topic": topic,
    "picoc": ai_picoc,
    "selected_synonyms": selected_for_query,  # only the facets you included
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
st.markdown("---")
st.download_button(
    "Download query bundle (JSON)",
    data=json.dumps(bundle, ensure_ascii=False, indent=2),
    file_name="arxiv_query_bundle.json",
    mime="application/json",
    use_container_width=True,
)
