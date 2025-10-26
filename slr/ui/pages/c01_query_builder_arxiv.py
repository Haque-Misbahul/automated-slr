# slr/ui/pages/c01_query_builder_arxiv.py

import sys, os, json, io, csv, math, time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import streamlit as st
from slr.query.builder import build_boolean_query

# NOTE: we won't depend on build_arxiv_query/arxiv_api_url anymore.
# We'll generate the arXiv query syntax ourselves in this file so it's consistent.

st.set_page_config(page_title="Conducting → Build & Gather (arXiv)", layout="wide")

# compact layout tweaks
st.markdown("""
<style>
div[data-testid="stHorizontalBlock"] > div { padding-right:.35rem !important; }
div[data-baseweb="input"] input { padding-top:6px; padding-bottom:6px; }
</style>
""", unsafe_allow_html=True)

st.markdown(
    "<h2 style='margin-top:25px;'>🔎 Conducting • Build Boolean Query & Gather Studies (arXiv)</h2>",
    unsafe_allow_html=True,
)

# -------------------------------------------------------------------
# 1. Read session data from Planning steps
# -------------------------------------------------------------------

topic    = st.session_state.get("topic", "")  # e.g. "sorting algorithm"
ai_picoc = st.session_state.get("ai_picoc")
ai_syns  = st.session_state.get("ai_syns")
selected_synonyms = st.session_state.get("selected_synonyms", {})

if topic:
    st.caption(f"From planning: **{topic}**")

if not ai_syns or not selected_synonyms:
    st.warning("No curated synonyms in session. Go to **Planning → Step 1** and curate facet synonyms first.")
    st.stop()

# -------------------------------------------------------------------
# 2. Facet selection (which synonym buckets we want to use)
# -------------------------------------------------------------------

st.subheader("Facet selection ↪︎")
all_facets = ["Population", "Intervention", "Comparison", "Outcome", "Context"]
include_facets = st.multiselect(
    "Include facets",
    options=all_facets,
    default=["Intervention", "Population"],
    help="Intervention=techniques (e.g. quick sort, merge sort). Population=things being sorted (array, dataset). Outcome/Context can over-constrain.",
)

selected_for_query = {f: selected_synonyms.get(f, []) for f in include_facets}
if not any(selected_for_query.values()):
    st.warning("Selected facets have no terms. Check your selections in Planning Step 1.")
    st.stop()

# -------------------------------------------------------------------
# 3. Target fields in arXiv
# -------------------------------------------------------------------

st.subheader("Target fields (arXiv)")
c1, c2, c3 = st.columns(3)
with c1:
    f_ti  = st.checkbox("Title (ti)",     value=True,  key="fld_ti")
with c2:
    f_abs = st.checkbox("Abstract (abs)", value=True,  key="fld_abs")
with c3:
    f_all = st.checkbox("All fields (all)", value=False, key="fld_all")

fields = []
if f_ti:
    fields.append("ti")
if f_abs:
    fields.append("abs")
if f_all:
    fields.append("all")

if not fields:
    st.warning("Select at least one field.")
    st.stop()

def _quote_if_needed(t: str) -> str:
    t = (t or "").strip()
    if not t:
        return ""
    t = t.replace('"', '\\"')
    if " " in t or "-" in t:
        return f"\"{t}\""
    return t

# -------------------------------------------------------------------
# 4. STRICT Boolean (for documentation)
# -------------------------------------------------------------------

# We try to call build_boolean_query with topic kwarg if supported.
try:
    strict_generic_query, strict_parts = build_boolean_query(
        selected_for_query,
        topic=topic,
    )
except TypeError:
    strict_generic_query, strict_parts = build_boolean_query(selected_for_query)

st.subheader("Strict Boolean (high precision)")
st.caption("Uses AND across conceptual facets. This is good for documentation / protocol, but can under-retrieve.")
st.code(strict_generic_query or "(empty)")

# -------------------------------------------------------------------
# 5. BROAD Recall Query (used for fetching)
#    Build a big OR bucket from:
#      - topic phrase
#      - Intervention terms
#      - Population terms
#      - (optionally other included facets)
# -------------------------------------------------------------------

def build_recall_term_list(topic_str: str, facet_terms_map: dict[str, list[str]]):
    pool = []
    # topic
    if topic_str:
        pool.append(topic_str)
    # then facet terms (Intervention first, then Population, then others)
    facet_priority = ["Intervention", "Population", "Comparison", "Outcome", "Context"]
    for facet in facet_priority:
        for term in facet_terms_map.get(facet, []) or []:
            pool.append(term)
    # normalize + dedup
    out = []
    seen = set()
    for raw in pool:
        qt = _quote_if_needed(raw)
        if not qt:
            continue
        key = qt.lower()
        if key not in seen:
            seen.add(key)
            out.append(qt)
    return out

recall_terms = build_recall_term_list(topic, selected_for_query)

if len(recall_terms) == 0:
    recall_boolean = ""
elif len(recall_terms) == 1:
    recall_boolean = recall_terms[0]
else:
    recall_boolean = "(" + " OR ".join(recall_terms) + ")"

st.subheader("Broad Recall Query (used for fetching)")
st.caption("Single OR bucket with topic + method names + key data structure words. This maximizes recall, like arXiv's own search box.")
st.code(recall_boolean or "(empty)")

# -------------------------------------------------------------------
# 6. Convert BROAD Recall Query into actual arXiv API 'search_query'
#
# arXiv syntax:
#   search_query=ti:"term" OR abs:"term" OR all:"term"
# We generate OR across all terms, expanding per field.
# -------------------------------------------------------------------

def build_arxiv_search_query(recall_terms_list, chosen_fields):
    """
    recall_terms_list  -> ['"sorting algorithm"', '"quick sort"', '"merge sort"', ...]
    chosen_fields      -> ['ti', 'abs', 'all'] etc.
    returns something like:
      (ti:"sorting algorithm" OR abs:"sorting algorithm" OR ti:"quick sort" OR abs:"quick sort" ...)
    """
    if not recall_terms_list or not chosen_fields:
        return ""

    per_term_chunks = []
    for term in recall_terms_list:
        # for each term build (ti:term OR abs:term ...)
        field_queries = []
        for fld in chosen_fields:
            field_queries.append(f'{fld}:{term}')
        if len(field_queries) == 1:
            per_term_chunks.append(field_queries[0])
        else:
            per_term_chunks.append("(" + " OR ".join(field_queries) + ")")

    # now OR across all terms
    if len(per_term_chunks) == 1:
        return per_term_chunks[0]
    return "(" + " OR ".join(per_term_chunks) + ")"

arxiv_query = build_arxiv_search_query(recall_terms, fields)

st.subheader("arXiv search_query ↪︎")
st.code(arxiv_query or "(empty)")

# -------------------------------------------------------------------
# 7. Build example API URL for display
#
#   http://export.arxiv.org/api/query?search_query=...&start=0&max_results=200
# -------------------------------------------------------------------

def build_arxiv_api_url(q: str, start: int = 0, max_results: int = 200, sort_by: str = None):
    import urllib.parse
    base = "http://export.arxiv.org/api/query"
    params = {
        "search_query": q,
        "start": str(start),
        "max_results": str(max_results),
    }
    if sort_by:
        # arXiv API supports sortBy=relevance|lastUpdatedDate|submittedDate
        params["sortBy"] = sort_by
    return base + "?" + urllib.parse.urlencode(params)

api_url_example = build_arxiv_api_url(arxiv_query, start=0, max_results=200)

st.markdown("**API URL (example):**")
st.markdown(f"[{api_url_example}]({api_url_example})")

# -------------------------------------------------------------------
# 8. Preview results (single page) using BROAD recall query
# -------------------------------------------------------------------

st.markdown("### Preview results (single page) ↪︎")
pc1, pc2, pc3 = st.columns(3)
with pc1:
    pv_max = st.number_input(
        "How many?",
        min_value=5,
        max_value=200,
        value=50,
        step=5,
        key="pv_max"
    )
with pc2:
    pv_start = st.number_input(
        "Start index",
        min_value=0,
        max_value=10000,
        value=0,
        step=10,
        key="pv_start"
    )
with pc3:
    pv_sort  = st.selectbox(
        "Sort by",
        ["relevance", "lastUpdatedDate", "submittedDate"],
        index=0,
        key="pv_sort"
    )

if st.button("Fetch preview", use_container_width=True):
    from slr.query.arxiv_api import fetch, build_url  # we'll keep using your helpers to actually call arXiv
    with st.spinner("Fetching from arXiv..."):
        # build_url() should accept our new query string
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

# -------------------------------------------------------------------
# 9. Gather STUDIES (all pages) using BROAD recall query
# -------------------------------------------------------------------

st.markdown("## 📥 Gather studies (all pages)")

g1, g2, g3 = st.columns(3)
with g1:
    page_size = st.number_input(
        "Page size (per API call)",
        min_value=10,
        max_value=200,
        value=100,
        step=10,
        help="arXiv supports large result sets. 100 is a good batch size."
    )
with g2:
    total_cap = st.number_input(
        "Total cap (max records)",
        min_value=50,
        max_value=5000,
        value=1000,
        step=50,
        help="Safety cap to avoid huge downloads."
    )
with g3:
    sleep_ms = st.number_input(
        "Politeness delay (ms)",
        min_value=0,
        max_value=2000,
        value=200,
        step=50,
        help="Delay between API calls so we don't hammer arXiv."
    )

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
    from slr.query.arxiv_api import fetch  # re-use your fetch()
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
                rows = fetch(
                    arxiv_query,
                    start=start,
                    max_results=int(page_size)
                )
            except Exception as e:
                st.error(f"Fetch error on batch {b}: {e}")
                break

        if not rows:
            # reached end
            break

        all_rows.extend(rows)
        total += len(rows)

        prog.progress(min(1.0, total / total_cap), text=f"Fetched {total} records")

        if sleep_ms > 0:
            time.sleep(sleep_ms / 1000.0)

        if len(rows) < page_size:
            break  # no more pages

    prog.progress(1.0, text=f"Done. Total collected: {total}")

    if not all_rows:
        st.warning("No records collected.")
    else:
        st.session_state["gathered_rows"] = all_rows

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

# -------------------------------------------------------------------
# 10. Bundle export for reproducibility
# -------------------------------------------------------------------

bundle = {
    "topic": topic,
    "picoc": ai_picoc,
    "selected_synonyms": selected_for_query,
    "strict_query": {
        "boolean": strict_generic_query,
        "parts": strict_parts,
        "note": "High-precision AND across facets. Kept for documentation / protocol."
    },
    "broad_recall_query": {
        "boolean": recall_boolean,
        "terms": recall_terms,
        "note": "Single OR bucket across topic + technique terms + population context. Used to retrieve the candidate pool.",
    },
    "arxiv": {
        "fields": fields,
        "search_query": arxiv_query,
        "api_url_example": api_url_example,
        "example_preview_start": 0,
        "example_preview_max_results": 200,
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
