# slr/ui/pages/c03_data_extraction.py
import sys, os, io, csv, json, re
from typing import List, Dict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
import streamlit as st

st.set_page_config(page_title="Conducting → Step 4: Data extraction", layout="wide")

# ---------- rerun helper (handles Streamlit versions) ----------
def force_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
        return
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
        return

# ---------- helpers ----------
def rows_to_csv(rows: List[Dict], cols: List[str]) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(cols)
    for r in rows:
        row = []
        for c in cols:
            v = r.get(c, "")
            if isinstance(v, list):
                v = ", ".join(v)
            row.append(v)
        w.writerow(row)
    return out.getvalue()

def to_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [str(v)]

def as_author_string(a) -> str:
    """Normalize authors to a single comma-separated string."""
    if isinstance(a, list):
        # list of strings or dicts {name: ...}
        norm = []
        for x in a:
            if isinstance(x, dict) and "name" in x:
                norm.append(str(x["name"]).strip())
            else:
                norm.append(str(x).strip())
        return ", ".join([s for s in norm if s])
    if a is None:
        return ""
    return str(a).strip()

def year_from_any(published: str, year: str) -> str:
    """Return year from either a 'published' string (YYYY-...) or explicit year."""
    if str(year).strip().isdigit() and len(str(year).strip()) == 4:
        return str(year).strip()
    if not published:
        return ""
    m = re.match(r"(\d{4})", str(published))
    return m.group(1) if m else ""

def pick_first(*vals) -> str:
    """Return first non-empty string among vals."""
    for v in vals:
        s = str(v or "").strip()
        if s:
            return s
    return ""

# ---------- load included studies ----------
topic = st.session_state.get("topic", "")
if topic:
    st.caption(f"Current topic: **{topic}**")

st.markdown("<h2 style='margin-top:20px;'>🗂️ Conducting • Step 4: Data extraction</h2>", unsafe_allow_html=True)

included = st.session_state.get("screened_rows", [])
if included:
    st.success(f"Loaded {len(included)} INCLUDED studies from session.")
else:
    up_inc = st.file_uploader("Upload INCLUDED studies (CSV or JSON) exported from Step 3", type=["csv", "json"])
    if up_inc:
        try:
            if (getattr(up_inc, "type", "") or "").endswith("/json") or up_inc.name.lower().endswith(".json"):
                included = json.loads(up_inc.read().decode("utf-8"))
            else:
                text = up_inc.read().decode("utf-8")
                reader = csv.DictReader(io.StringIO(text))
                included = list(reader)
            st.success(f"Loaded {len(included)} INCLUDED studies from upload.")
        except Exception as e:
            st.error(f"Failed to parse included list: {e}")

if not included:
    st.info("No included studies. Finish **Conducting · Step 3** first or upload data above.")
    st.stop()

# ---------- load extraction form schema from planning (Step 6) ----------
schema = st.session_state.get("extraction_form")
if not schema or not isinstance(schema, dict) or not schema.get("fields"):
    # Minimal fallback schema (exactly what Step 6 now defines)
    schema = {
        "fields": [
            {"name": "Title",          "key": "title",    "type": "text",     "required": True,  "help": "Paper title"},
            {"name": "Authors",        "key": "authors",  "type": "longtext", "required": True,  "help": "Comma-separated"},
            {"name": "Year",           "key": "year",     "type": "number",   "required": True,  "help": "Publication year"},
            {"name": "DOI / arXiv ID", "key": "id",       "type": "text",     "required": True,  "help": "DOI or arXiv identifier"},
            {"name": "URL",            "key": "url",      "type": "url",      "required": True,  "help": "Landing page"},
            {"name": "Abstract",       "key": "abstract", "type": "longtext", "required": True,  "help": "Paper abstract"},
        ]
    }

fields: List[Dict] = schema.get("fields", [])
if not fields:
    st.error("Extraction schema has no fields. Go to **Planning → Step 6** to define the form.")
    st.stop()

st.markdown("### Extraction schema")
with st.expander("Show fields", expanded=False):
    st.json(schema)

# ---------- session storage for entered data ----------
extracted: Dict[str, Dict] = st.session_state.get("extracted_data", {})

# ---------- paper navigator ----------
st.markdown("### Extract per paper")
titles = [str(r.get("title", "")) for r in included]
if "extract_idx" not in st.session_state:
    st.session_state["extract_idx"] = 0

cols_top = st.columns([5, 1, 1])
with cols_top[0]:
    st.write("Use **Prev/Next** to navigate; values auto-save to session.")
with cols_top[1]:
    if st.button("⬅️ Prev", use_container_width=True):
        st.session_state["extract_idx"] = max(0, st.session_state["extract_idx"] - 1)
        force_rerun()
with cols_top[2]:
    if st.button("Next ➡️", use_container_width=True):
        st.session_state["extract_idx"] = min(len(included) - 1, st.session_state["extract_idx"] + 1)
        force_rerun()

idx = st.session_state["extract_idx"]
paper = included[idx]

# ---- prefill from source row (arXiv-friendly) ----
pid = pick_first(
    paper.get("id"),
    paper.get("arxiv_id"),
    paper.get("doi"),
    f"paper_{idx}"
)

prefilled: Dict[str, str] = {
    "id": pid,
    "title": str(paper.get("title", "")),
    "authors": as_author_string(paper.get("authors")),
    "year": year_from_any(paper.get("published", ""), paper.get("year", "")),
    "url": pick_first(paper.get("url"), paper.get("link"), paper.get("pdf_url")),
    "abstract": pick_first(paper.get("abstract"), paper.get("summary")),
}

# If an explicit id-like field exists and our pid is not in the record yet, also set it:
if not prefilled["id"]:
    prefilled["id"] = pid

# merge existing extracted (user edits win)
current_record = dict(prefilled)
current_record.update(extracted.get(pid, {}))

# Helpful heading with link if available
paper_link = pick_first(paper.get("url"), paper.get("link"))
title_for_header = paper.get("title","(no title)")
if paper_link:
    st.markdown(f"**Paper {idx+1} / {len(included)}** — [{title_for_header}]({paper_link})")
else:
    st.markdown(f"**Paper {idx+1} / {len(included)}** — {title_for_header}")

# ---------- render form ----------
with st.form(key=f"extract_form_{pid}", clear_on_submit=False):
    new_values: Dict[str, str] = {"id": pid}
    for f in fields:
        fname = f.get("name", f.get("key",""))
        fkey = f.get("key", fname.lower().replace(" ", "_"))
        ftype = (f.get("type", "text") or "text").lower()
        freq  = bool(f.get("required", False))
        fhelp = f.get("help", "")
        choices = to_list(f.get("choices", []))
        default_val = current_record.get(fkey, "")

        # unique key per paper+field so widgets reset on navigation
        wkey = f"{fkey}_{pid}"

        if ftype == "number":
            try:
                default_num = int(str(default_val)) if str(default_val).strip() != "" else 0
            except Exception:
                default_num = 0
            val = st.number_input(f"{fname}" + (" *" if freq else ""), value=default_num, step=1, help=fhelp, key=wkey)
            new_values[fkey] = val

        elif ftype == "boolean":
            val = st.checkbox(f"{fname}" + (" *" if freq else ""), value=bool(default_val), help=fhelp, key=wkey)
            new_values[fkey] = val

        elif ftype == "select" and choices:
            if default_val not in choices and choices:
                default_val = choices[0]
            idx_choice = choices.index(default_val) if default_val in choices else 0
            val = st.selectbox(f"{fname}" + (" *" if freq else ""), choices, index=idx_choice, help=fhelp, key=wkey)
            new_values[fkey] = val

        elif ftype == "longtext":
            val = st.text_area(f"{fname}" + (" *" if freq else ""), value=str(default_val), height=160, help=fhelp, key=wkey)
            new_values[fkey] = val

        else:
            # text/url/date/etc. -> simple text input
            val = st.text_input(f"{fname}" + (" *" if freq else ""), value=str(default_val), help=fhelp, key=wkey)
            new_values[fkey] = val

    submitted = st.form_submit_button("💾 Save this paper", use_container_width=True)

if submitted:
    extracted[pid] = new_values
    st.session_state["extracted_data"] = extracted
    st.success("Saved.")

# ---------- quick jump ----------
with st.expander("Jump to a specific paper", expanded=False):
    target = st.selectbox("Select paper", [f"{i+1}. {titles[i][:80]}" for i in range(len(titles))], index=idx)
    jump_idx = int(target.split(".")[0]) - 1
    if st.button("Go", key="jump_btn"):
        st.session_state["extract_idx"] = jump_idx
        force_rerun()

# ---------- exports ----------
st.markdown("---")
st.subheader("Export")

cols = ["id"] + [f.get("key") for f in fields]
table: List[Dict] = []
for r in included:
    pid_i = pick_first(r.get("id"), r.get("arxiv_id"), r.get("doi"))
    if not pid_i:
        pid_i = ""
    base = {"id": pid_i}
    base.update(st.session_state.get("extracted_data", {}).get(pid_i, {}))
    for k in cols:
        if k not in base:
            base[k] = ""
    table.append(base)

csv_blob  = rows_to_csv(table, cols)
json_blob = json.dumps(table, ensure_ascii=False, indent=2)

c1, c2, c3 = st.columns(3)
with c1:
    st.download_button("⬇️ Download extracted (CSV)", data=csv_blob, file_name="extracted_data.csv",
                       mime="text/csv", use_container_width=True)
with c2:
    st.download_button("⬇️ Download extracted (JSON)", data=json_blob, file_name="extracted_data.json",
                       mime="application/json", use_container_width=True)
with c3:
    blank_rows = [{"id": pick_first(r.get("id"), r.get("arxiv_id"), r.get("doi")) or ""} for r in included]
    blank_cols = ["id"] + [f.get("key") for f in fields]
    blank_csv = rows_to_csv(blank_rows, blank_cols)
    st.download_button("⬇️ Download blank template (CSV)", data=blank_csv, file_name="extraction_template.csv",
                       mime="text/csv", use_container_width=True)

st.caption(
    "Widgets are keyed per paper so they reset on navigation. "
    "Authors/Year/URL/Abstract are prefilled when available from arXiv metadata."
)
