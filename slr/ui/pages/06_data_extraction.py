import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import json, csv, io
import streamlit as st

# ---------------- Page setup ----------------
st.set_page_config(page_title="Planning → Step 6: Data Extraction Form", layout="wide")
st.markdown(
    "<h2 style='margin-top:25px;'>📋 Planning • Step 6: Design the Data Extraction Form</h2>",
    unsafe_allow_html=True,
)

# Compact layout & subtle styling
st.markdown("""
<style>
div[data-testid="stHorizontalBlock"] > div { padding-right:.35rem !important; }
div[data-baseweb="input"] input { padding-top:6px; padding-bottom:6px; }
.group { font-weight:600; margin-top:.75rem; color:#374151; }
.item { padding:.40rem .60rem; border-radius:.50rem; background:#f8fafc; }
.item + .item { margin-top:.35rem; }
.keyhint { color:#6b7280; font-size:12px; margin-left:.35rem; }
</style>
""", unsafe_allow_html=True)

topic   = st.session_state.get("topic", "")
if topic:
    st.caption(f"Current topic: **{topic}**")
st.markdown("---")

st.write(
    "This form uses a **minimal arXiv-friendly field set**. "
    "Select which fields to include in your extraction. "
    "Types and required flags are predefined for clean export."
)

# ---------------- Fixed minimal fields ----------------
FIXED_FIELDS = [
    {"name":"Title",          "key":"title",    "type":"text",     "required":True,  "desc":"Paper title"},
    {"name":"Authors",        "key":"authors",  "type":"longtext", "required":True,  "desc":"Comma-separated"},
    {"name":"Year",           "key":"year",     "type":"number",   "required":True,  "desc":"Publication year"},
    {"name":"DOI / arXiv ID", "key":"id",       "type":"text",     "required":True,  "desc":"DOI or arXiv identifier"},
    {"name":"URL",            "key":"url",      "type":"url",      "required":True,  "desc":"Landing page"},
    {"name":"Abstract",       "key":"abstract", "type":"longtext", "required":True,  "desc":"Paper abstract"},
]

# Load previous selection (if any)
saved = st.session_state.get("extraction_form")
prev_keys = set([f["key"] for f in saved["fields"]]) if isinstance(saved, dict) and "fields" in saved else set(k["key"] for k in FIXED_FIELDS)

st.subheader("Fields")
st.caption("Tick to include. (Names, keys, types, and required flags are fixed for consistency.)")

selected = []
for i, f in enumerate(FIXED_FIELDS):
    with st.container():
        col = st.columns([0.08, 0.92])
        with col[0]:
            keep = st.checkbox("", value=(f["key"] in prev_keys), key=f"keep_{i}")
        with col[1]:
            st.markdown(f"<div class='item'><strong>{f['name']}</strong>"
                        f"<span class='keyhint'>[{f['key']} • {f['type']} • {'required' if f['required'] else 'optional'}]</span></div>",
                        unsafe_allow_html=True)
    if keep:
        selected.append(f)

if not selected:
    st.warning("No fields selected. Choose at least one to continue.")

st.markdown("---")

# --------- Save to session ---------
if st.button("Save form to session", use_container_width=True):
    st.session_state["extraction_form"] = {
        "fields": selected,
        "notes": "Planning artifact (minimal set).",
    }
    st.success("Saved data extraction form.")

# --------- Export helpers ---------
def to_json_schema(fields):
    props, required = {}, []
    for f in fields:
        t = f["type"]
        js_type = {
            "text":"string","longtext":"string","url":"string","date":"string",
            "number":"number","boolean":"boolean","select":"string","multiselect":"array"
        }[t]
        p = {"type": js_type, "title": f["name"], "description": f.get("desc","")}
        if t == "multiselect":
            p["items"] = {"type":"string"}
        if "choices" in f:
            p["enum"] = f["choices"]
        props[f["key"]] = p
        if f.get("required"):
            required.append(f["key"])
    return {
        "$schema":"https://json-schema.org/draft/2020-12/schema",
        "title":"SLR Data Extraction Schema (Minimal)",
        "type":"object",
        "properties": props,
        "required": required
    }

def csv_template(fields):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([f["key"] for f in fields])
    return out.getvalue()

# Use current selection or default
export_fields = selected if selected else FIXED_FIELDS

schema = to_json_schema(export_fields)
csv_hdr = csv_template(export_fields)

st.subheader("Export")
st.download_button(
    "Download JSON schema",
    data=json.dumps(schema, ensure_ascii=False, indent=2),
    file_name="slr_extraction_schema_min.json",
    mime="application/json",
    use_container_width=True,
)
st.download_button(
    "Download CSV template (header only)",
    data=csv_hdr,
    file_name="slr_extraction_template_min.csv",
    mime="text/csv",
    use_container_width=True,
)

st.info(
    "This **minimal** Data Extraction Form includes: "
    "**Title, Authors, Year, DOI/arXiv ID, URL, Abstract**. "
    "You can extend it later if your professor requests more fields."
)
