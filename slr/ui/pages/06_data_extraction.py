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

# optional compact layout
st.markdown("""
<style>
div[data-testid="stHorizontalBlock"] > div { padding-right:.35rem !important; }
div[data-baseweb="input"] input { padding-top:6px; padding-bottom:6px; }
small.help { color:#6b7280; }
.badge { background:#eef2ff; color:#4338ca; padding:2px 8px; border-radius:9999px; font-size:12px; }
.group { font-weight:600; margin-top:.75rem; color:#374151; }
</style>
""", unsafe_allow_html=True)

topic   = st.session_state.get("topic", "")
picoc   = st.session_state.get("ai_picoc", {})
rqs     = st.session_state.get("rqs", [])
sources = st.session_state.get("sources", {})
criteria = st.session_state.get("criteria", {})
qchk    = st.session_state.get("quality_checklist", {})

if topic:
    st.caption(f"Current topic: **{topic}**")
st.markdown("---")

st.write(
    "Define the **fields you will extract** from each included study in the conducting phase. "
    "You can keep defaults, edit names, set field types, mark **required**, and add **choices** for select fields. "
    "Exports include a JSON schema and a CSV template."
)

# ---------------- Field model ----------------
TYPES = ["text", "longtext", "number", "boolean", "date", "url", "select", "multiselect"]

DEFAULT_FIELDS = [
    # Bibliographic
    {"group":"Bibliographic", "name":"Title",           "key":"title",         "type":"text",      "required":True,  "desc":"Paper title"},
    {"group":"Bibliographic", "name":"Authors",         "key":"authors",       "type":"longtext",  "required":True,  "desc":"Comma-separated"},
    {"group":"Bibliographic", "name":"Year",            "key":"year",          "type":"number",    "required":True,  "desc":"Publication year"},
    {"group":"Bibliographic", "name":"Venue",           "key":"venue",         "type":"text",      "required":False, "desc":"Journal/Conference"},
    {"group":"Bibliographic", "name":"DOI / arXiv ID",  "key":"id",            "type":"text",      "required":False, "desc":"DOI or arXiv identifier"},
    {"group":"Bibliographic", "name":"URL",             "key":"url",           "type":"url",       "required":False, "desc":"Landing page"},

    # Mapping to protocol
    {"group":"Protocol mapping", "name":"Population (PICOC)",    "key":"picoc_population",   "type":"text", "required":False, "desc":"Extracted population"},
    {"group":"Protocol mapping", "name":"Intervention (PICOC)",  "key":"picoc_intervention", "type":"text", "required":True,  "desc":"Technique/approach"},
    {"group":"Protocol mapping", "name":"Comparison (PICOC)",    "key":"picoc_comparison",   "type":"text", "required":False, "desc":"Baselines/alternatives"},
    {"group":"Protocol mapping", "name":"Outcome (PICOC)",       "key":"picoc_outcome",      "type":"text", "required":True,  "desc":"Targeted outcomes/metrics"},
    {"group":"Protocol mapping", "name":"Context (PICOC)",       "key":"picoc_context",      "type":"text", "required":False, "desc":"Env/domain context"},
    {"group":"Protocol mapping", "name":"Relevant RQ(s)",        "key":"rq_links",           "type":"longtext", "required":False, "desc":"Which RQs this study informs"},

    # Method & data
    {"group":"Method & Data", "name":"Study type",   "key":"study_type", "type":"select", "required":True,
     "choices":["Empirical","Experimental","Theoretical","Systematic Review","Mapping Study","Case Study"] , "desc":"Classification"},
    {"group":"Method & Data", "name":"Dataset / Subjects", "key":"dataset", "type":"longtext", "required":False, "desc":"Dataset(s) or subjects"},
    {"group":"Method & Data", "name":"Tasks",       "key":"tasks",     "type":"longtext", "required":False, "desc":"Tasks/problems addressed"},
    {"group":"Method & Data", "name":"Baseline(s)", "key":"baselines", "type":"longtext", "required":False, "desc":"Comparison methods"},
    {"group":"Method & Data", "name":"Metrics",     "key":"metrics",   "type":"longtext", "required":True,  "desc":"e.g., F1, accuracy, MAPE, latency"},

    # Results & reproducibility
    {"group":"Results", "name":"Main findings", "key":"findings", "type":"longtext", "required":True,  "desc":"Key results"},
    {"group":"Results", "name":"Effect on Outcome", "key":"effect_on_outcome", "type":"text", "required":False, "desc":"Direction/size (qual.)"},
    {"group":"Results", "name":"Code available", "key":"code_available", "type":"boolean", "required":False, "desc":"Artifact or repo available"},
    {"group":"Results", "name":"Threats to validity", "key":"threats", "type":"longtext", "required":False, "desc":"Internal/external/construct"},

    # Screening linkage
    {"group":"Screening", "name":"Quality score", "key":"quality_score", "type":"number",  "required":False, "desc":"Total QAC score"},
    {"group":"Screening", "name":"Include (final)", "key":"include_final", "type":"boolean","required":True,  "desc":"Final include decision"},
    {"group":"Screening", "name":"Notes", "key":"notes", "type":"longtext", "required":False, "desc":"Reviewer notes"},
]

# load previous
saved = st.session_state.get("extraction_form")
fields = saved["fields"] if isinstance(saved, dict) and "fields" in saved else DEFAULT_FIELDS.copy()

st.subheader("Fields")
st.caption("Uncheck to drop. You can edit name/key/type/required and choices (for select types).")

new_fields = []
curr_group = None

for i, f in enumerate(fields):
    group = f.get("group") or "General"
    if group != curr_group:
        st.markdown(f"<div class='group'>{group}</div>", unsafe_allow_html=True)
        curr_group = group

    c0, c1, c2, c3, c4 = st.columns([0.06, 0.28, 0.20, 0.16, 0.30], gap="small")
    with c0:
        keep = st.checkbox(" ", value=True, key=f"keep_{i}")
    with c1:
        name = st.text_input(f"name_{i}", value=f.get("name",""), label_visibility="collapsed")
    with c2:
        key  = st.text_input(f"key_{i}",  value=f.get("key",""),  label_visibility="collapsed")
    with c3:
        ftype = st.selectbox(f"type_{i}", TYPES, index=TYPES.index(f.get("type","text")))
        required = st.checkbox("Req", value=bool(f.get("required", False)), key=f"req_{i}")
    with c4:
        desc = st.text_input(f"desc_{i}", value=f.get("desc",""), label_visibility="collapsed")

    item = {"group":group, "name":name, "key":key, "type":ftype, "required":required, "desc":desc}
    if ftype in ("select","multiselect"):
        choices_default = ", ".join(f.get("choices", []))
        choices_str = st.text_input(f"choices_{i}", value=choices_default, placeholder="choice1, choice2, ...")
        item["choices"] = [c.strip() for c in choices_str.split(",") if c.strip()]

    if keep and name.strip() and key.strip():
        new_fields.append(item)

st.markdown("---")

st.subheader("Add custom field")
cc1, cc2, cc3, cc4 = st.columns([0.28, 0.20, 0.16, 0.36], gap="small")
with cc1:
    c_name = st.text_input("Field name", value="", placeholder="e.g., Hardware/Environment")
with cc2:
    c_key  = st.text_input("Key", value="", placeholder="hardware_env")
with cc3:
    c_type = st.selectbox("Type", TYPES, index=0, key="c_type")
with cc4:
    c_desc = st.text_input("Description", value="", placeholder="What to capture")
c_req = st.checkbox("Required", value=False, key="c_req")
if c_type in ("select","multiselect"):
    c_choices_str = st.text_input("Choices (comma-separated)", value="", key="c_choices")
else:
    c_choices_str = ""

if st.button("➕ Add field"):
    if c_name.strip() and c_key.strip():
        item = {"group":"Custom", "name":c_name.strip(), "key":c_key.strip(),
                "type":c_type, "required":c_req, "desc":c_desc.strip()}
        if c_type in ("select","multiselect") and c_choices_str.strip():
            item["choices"] = [x.strip() for x in c_choices_str.split(",") if x.strip()]
        new_fields.append(item)
        st.success(f"Added field: {c_name.strip()}")

# --------- Save to session ---------
if st.button("Save form to session", use_container_width=True):
    st.session_state["extraction_form"] = {
        "fields": new_fields,
        "notes": "Planning artifact. Use to build screening/extraction spreadsheets or forms."
    }
    st.success("Saved data extraction form.")

# --------- Export: JSON schema + CSV template ---------
def to_json_schema(fields):
    props = {}
    required = []
    for f in fields:
        t = f["type"]
        js_type = {"text":"string","longtext":"string","url":"string","date":"string",
                   "number":"number","boolean":"boolean","select":"string","multiselect":"array"}[t]
        p = {"type": js_type, "title": f["name"], "description": f.get("desc","")}
        if t == "multiselect":
            p["items"] = {"type":"string"}
        if "choices" in f:
            p["enum"] = f["choices"]
        props[f["key"]] = p
        if f.get("required"):
            required.append(f["key"])
    return {"$schema":"https://json-schema.org/draft/2020-12/schema",
            "title":"SLR Data Extraction Schema",
            "type":"object",
            "properties": props,
            "required": required}

def csv_template(fields):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([f["key"] for f in fields])
    return out.getvalue()

schema = to_json_schema(new_fields)
csv_hdr = csv_template(new_fields)

st.subheader("Export")
st.download_button(
    "Download JSON schema",
    data=json.dumps(schema, ensure_ascii=False, indent=2),
    file_name="slr_extraction_schema.json",
    mime="application/json",
    use_container_width=True,
)
st.download_button(
    "Download CSV template (header only)",
    data=csv_hdr,
    file_name="slr_extraction_template.csv",
    mime="text/csv",
    use_container_width=True,
)

st.info(
    "You now have a **Data Extraction Form** definition. "
    "In the conducting phase, you’ll use this to structure spreadsheets or build a small UI to capture data per study."
)
