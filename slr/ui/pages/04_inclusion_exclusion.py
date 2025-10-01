import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import json
import streamlit as st

# ---------------- Page setup ----------------
st.set_page_config(page_title="Planning → Step 4: Inclusion/Exclusion", layout="wide")
st.markdown(
    "<h2 style='margin-top:25px;'>✅ Planning • Step 4: Define Inclusion / Exclusion Criteria</h2>",
    unsafe_allow_html=True,
)
st.markdown("""
<style>
/* shrink column gaps in 2-column rows we use for criteria lines */
div[data-testid="stHorizontalBlock"] > div { padding-right: .25rem !important; }
/* slightly tighter text inputs so they align nicer with the checkbox */
div[data-baseweb="input"] input { padding-top: 6px; padding-bottom: 6px; }
</style>
""", unsafe_allow_html=True)


# Optional: pick up shared CSS if you have it
for css_name in ("styles.css", "style.css"):
    css_path = os.path.join(os.path.dirname(__file__), "..", css_name)
    css_path = os.path.abspath(css_path)
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
        break

topic   = st.session_state.get("topic", "")
picoc   = st.session_state.get("ai_picoc", {})
sources = st.session_state.get("sources", {})

if topic:
    st.caption(f"Current topic: **{topic}**")
st.markdown("---")

st.write(
    "Predefine **Inclusion** and **Exclusion** rules to avoid bias during screening. "
    "You can select common criteria and add custom ones."
)

# ---------------- Default criteria ----------------
DEFAULT_INCLUSION = [
    "Study is within **Computer Science** domain",
    "Study addresses the defined **Intervention** and fits the PICOC scope",
    "Full text is accessible (preprint or open access)",
    "Written in English",
    "Published in the selected source(s) (e.g., arXiv with chosen CS categories)",
    "Publication type is research (empirical, experimental, theoretical, or systematic review)",
]

DEFAULT_EXCLUSION = [
    "Out of scope (topic not aligned with PICOC)",
    "Non-CS domain (e.g., physics/biology) without CS relevance",
    "Non-research material (editorial, poster, tutorial, keynote, thesis, blog)",
    "Duplicate versions of the same paper",
    "Insufficient information (missing abstract/full text)",
    "Non-English text",
]

# Load prior from session if any
saved_crit = st.session_state.get("criteria", {})
incl_selected = saved_crit.get("include", DEFAULT_INCLUSION)
excl_selected = saved_crit.get("exclude", DEFAULT_EXCLUSION)
year_from = saved_crit.get("year_from", 2015)
year_to   = saved_crit.get("year_to", 2025)

# ---------------- Time window (optional but common) ----------------
st.subheader("Time window (optional)")
c1, c2 = st.columns(2)
with c1:
    year_from = st.number_input("From year", min_value=1990, max_value=2100, value=int(year_from), step=1)
with c2:
    year_to   = st.number_input("To year",   min_value=1990, max_value=2100, value=int(year_to),   step=1)
if year_from > year_to:
    st.warning("`From year` must be ≤ `To year`.")

st.markdown("---")

# ---------------- Checklists ----------------
st.subheader("Inclusion criteria")
st.caption("Tick what applies. You can edit text inline.")

new_incl = []
for i, rule in enumerate(incl_selected):
    c1, c2 = st.columns([0.05, 0.95], gap="small")
    with c1:
        keep = st.checkbox(" ", value=True, key=f"incl_chk_{i}")
    with c2:
        txt = st.text_input(f"incl_txt_label_{i}", value=rule, key=f"incl_txt_{i}", label_visibility="collapsed")
    if keep and txt.strip():
        new_incl.append(txt.strip())

if st.button("➕ Add empty inclusion", key="btn_add_incl"):
    new_incl.append("")

if len(new_incl) < 5:
    st.warning(f"Selected {len(new_incl)} inclusion criteria (< 5). Consider adding more for robustness.")


st.subheader("Exclusion criteria")
st.caption("Tick what applies. You can edit text inline.")

new_excl = []
for i, rule in enumerate(excl_selected):
    c1, c2 = st.columns([0.05, 0.95], gap="small")
    with c1:
        keep = st.checkbox(" ", value=True, key=f"excl_chk_{i}")
    with c2:
        txt = st.text_input(f"excl_txt_label_{i}", value=rule, key=f"excl_txt_{i}", label_visibility="collapsed")
    if keep and txt.strip():
        new_excl.append(txt.strip())

if st.button("➕ Add empty exclusion", key="btn_add_excl"):
    new_excl.append("")

if len(new_excl) < 5:
    st.warning(f"Selected {len(new_excl)} exclusion criteria (< 5). Consider adding more for clarity.")


# ---------------- Custom free-form adds ----------------
st.subheader("Add custom criteria")
c3, c4 = st.columns(2)
with c3:
    custom_incl = st.text_input("Custom inclusion", value="", placeholder="e.g., Study reports evaluation metrics relevant to Outcome")
    if st.button("Add inclusion"):
        if custom_incl.strip():
            new_incl.append(custom_incl.strip())
with c4:
    custom_excl = st.text_input("Custom exclusion", value="", placeholder="e.g., Preprints without method description")
    if st.button("Add exclusion"):
        if custom_excl.strip():
            new_excl.append(custom_excl.strip())

# Ensure we still have at least 5 criteria each (as requested)
def ensure_minimum(lst, defaults, minimum=5):
    out = [x for x in lst if x.strip()]
    if len(out) < minimum:
        for d in defaults:
            if d not in out:
                out.append(d)
            if len(out) >= minimum:
                break
    return out

new_incl = ensure_minimum(new_incl, DEFAULT_INCLUSION, minimum=5)
new_excl = ensure_minimum(new_excl, DEFAULT_EXCLUSION, minimum=5)

# ---------------- Save + Export ----------------
if st.button("Save criteria to session", use_container_width=True):
    st.session_state["criteria"] = {
        "include": new_incl,
        "exclude": new_excl,
        "year_from": int(year_from),
        "year_to": int(year_to),
    }
    st.success("Saved inclusion/exclusion criteria.")

st.subheader("Current snapshot")
st.write("**Inclusion (≥5):**")
st.markdown("\n".join([f"- {r}" for r in new_incl]) or "_None_")
st.write("**Exclusion (≥5):**")
st.markdown("\n".join([f"- {r}" for r in new_excl]) or "_None_")
st.write(f"**Years:** {year_from}–{year_to}")

bundle = {
    "topic": topic,
    "picoc": picoc,
    "sources": sources,
    "criteria": {
        "include": new_incl,
        "exclude": new_excl,
        "year_from": int(year_from),
        "year_to": int(year_to),
    },
}

st.download_button(
    "Download criteria (JSON)",
    data=json.dumps(bundle, ensure_ascii=False, indent=2),
    file_name="slr_criteria.json",
    mime="application/json",
    use_container_width=True,
)

# Markdown export for protocol
md = ["# Inclusion and Exclusion Criteria", ""]
md.append("## Inclusion")
md += [f"- {r}" for r in new_incl]
md += ["", "## Exclusion"]
md += [f"- {r}" for r in new_excl]
md += ["", "## Years", f"- {year_from}–{year_to}"]
st.download_button(
    "Download criteria (Markdown)",
    data="\n".join(md),
    file_name="slr_criteria.md",
    mime="text/markdown",
    use_container_width=True,
)

st.info("Next planning step: **Step 5 – Quality assessment checklist**.")
