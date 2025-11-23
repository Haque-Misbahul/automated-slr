import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import json
import re
import streamlit as st
from slr.agents.criteria import generate_criteria_from_picoc
from slr.ui.theme import inject_css
# -------- helpers --------

def _shorten_rule(text: str) -> str:
    """
    Make a rule concise:
    - remove anything after ';'
    - drop parentheticals (...)
    - drop 'e.g.' and following details
    - collapse spaces
    - strip trailing '.'
    """
    if not text:
        return ""

    t = text.strip()

    # drop everything after ';'
    t = t.split(";")[0]

    # remove (...) explanatory asides
    t = re.sub(r"\([^)]*\)", "", t)

    # remove 'e.g.' and what follows
    t = re.sub(r"\b(e\.g\.|for example|such as)\b.*", "", t, flags=re.IGNORECASE)

    # collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()

    if t.endswith("."):
        t = t[:-1].strip()

    return t

def _shorten_rules_list(rules):
    out = []
    seen = set()
    for r in rules:
        s = _shorten_rule(r)
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out

def ensure_minimum(lst, minimum=5, fallback_sentence="Relevant to the defined technical scope"):
    out = [x for x in lst if x.strip()]
    while len(out) < minimum:
        out.append(fallback_sentence)
    return out

# -------- page setup --------

st.set_page_config(page_title="Planning → Step 4: Inclusion / Exclusion", layout="wide")
inject_css()
st.markdown(
    "<h2 style='margin-top:25px;'>Planning • Step 4: Define Inclusion / Exclusion Criteria</h2>",
    unsafe_allow_html=True,
)

st.markdown("""
<style>
div[data-testid="stHorizontalBlock"] > div { padding-right: .5rem !important; }
div[data-baseweb="input"] input { padding-top: 6px; padding-bottom: 6px; }
label[data-baseweb="checkbox"] { font-size: 0.9rem; }
/* make delete buttons tight */
button[kind="secondary"] div[data-testid="stMarkdownContainer"] {
    font-size: 0.8rem;
}
</style>
""", unsafe_allow_html=True)

# pick up shared CSS if present
for css_name in ("styles.css", "style.css"):
    css_path = os.path.join(os.path.dirname(__file__), "..", css_name)
    css_path = os.path.abspath(css_path)
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
        break

# -------- session context --------

topic    = st.session_state.get("topic", "")
picoc    = st.session_state.get("ai_picoc", {})
sources  = st.session_state.get("sources", {})
syns     = st.session_state.get("selected_synonyms", {})

if not picoc:
    st.warning("No PICOC found in session. Please go to **Step 1** first.")
    st.stop()

if topic:
    st.caption(f"Current topic: **{topic}**")

st.write(
    "We'll auto-generate Inclusion and Exclusion criteria based on your PICOC and "
    "then you can refine them. Keep them short and actionable."
)

st.markdown("---")

# -------- init criteria in session --------

if "criteria" not in st.session_state:
    st.session_state["criteria"] = {
        "include": [],
        "exclude": [],
        "year_from": None,
        "year_to": None,
    }

crit_state = st.session_state["criteria"]

# -------- generate draft block --------
# (subheader optional; keep or remove as you like)
# st.subheader("Auto-generate criteria from PICOC + synonyms ↪")

# 3 columns, middle one is 3x wider → like using middle 3 of 5
# -------- generate draft block --------
c1, c_mid, c3 = st.columns([1, 3, 1])

with c_mid:
    if st.button(
        " Generate inclusion/exclusion Criteria",
        use_container_width=True,
        help="Click to generate Inclusion/Exclusion criteria",
    ):
        with st.spinner("Generating draft criteria…"):
            try:
                draft = generate_criteria_from_picoc(picoc, syns)
            except Exception as e:
                st.error(f"Criteria generation failed: {e}")
                draft = {
                    "include": crit_state.get("include", []),
                    "exclude": crit_state.get("exclude", []),
                    "years": {
                        "from": crit_state.get("year_from"),
                        "to": crit_state.get("year_to"),
                    },
                }

        inc_short = _shorten_rules_list(draft.get("include", []))
        exc_short = _shorten_rules_list(draft.get("exclude", []))

        yrs = draft.get("years", {}) or {}
        yr_from = yrs.get("from", crit_state.get("year_from"))
        yr_to   = yrs.get("to",   crit_state.get("year_to"))

        st.session_state["criteria"] = {
            "include": inc_short,
            "exclude": exc_short,
            "year_from": yr_from,
            "year_to": yr_to,
        }
        crit_state = st.session_state["criteria"]


st.markdown("""
<style>
/* Make ALL buttons on this page light sky blue + bigger label */
div[data-testid="stButton"] button {
    background-color: #e0f4ff !important;  /* light sky blue */
    border-color: #b5ddff !important;      /* slightly darker border */
}

/* bump label size a bit */
div[data-testid="stButton"] button p {
    font-size: 1.15rem !important;
}
</style>
""", unsafe_allow_html=True)







# refresh local refs in case we just regenerated:
incl_selected = list(crit_state.get("include", []))
excl_selected = list(crit_state.get("exclude", []))
year_from     = crit_state.get("year_from", None)
year_to       = crit_state.get("year_to", None)

if year_from is None:
    year_from = 2015
if year_to is None:
    year_to = 2025

# -------- year range --------

# st.subheader("Time window (optional)")
# yr1, yr2 = st.columns(2)
# with yr1:
#     year_from = st.number_input(
#         "From year",
#         min_value=1990,
#         max_value=2100,
#         value=int(year_from),
#         step=1,
#         help="Only include studies published on/after this year (optional)."
#     )
# with yr2:
#     year_to   = st.number_input(
#         "To year",
#         min_value=1990,
#         max_value=2100,
#         value=int(year_to),
#         step=1,
#         help="Only include studies published on/before this year (optional)."
#     )

# if year_from > year_to:
#     st.warning("`From year` must be ≤ `To year`.")

# st.markdown("---")

# -------- criteria editing (with delete buttons) --------

st.subheader("Inclusion vs Exclusion")

cols_main = st.columns(2)

# We'll collect fresh edited lists here:
edited_incl = []
edited_excl = []

# LEFT: Inclusion
with cols_main[0]:
    st.markdown("**Inclusion criteria**")
    st.caption("Edit wording directly. Click 🗑 to remove a rule.")

    for i, rule in enumerate(incl_selected):
        row_c1, row_c2 = st.columns([0.9, 0.1], gap="small")

        with row_c1:
            txt = st.text_area(
                f"incl_txt_input_{i}",
                value=rule,
                key=f"incl_txt_key_{i}",
                height=64,
                label_visibility="collapsed",
            )

        # delete button for this row
        with row_c2:
            delete_clicked = st.button("🗑", key=f"incl_del_{i}", help="Remove this inclusion rule")
        # keep if not deleted AND not empty
        if not delete_clicked and txt.strip():
            edited_incl.append(txt.strip())

# RIGHT: Exclusion
with cols_main[1]:
    st.markdown("**Exclusion criteria**")
    st.caption("Edit wording directly. Click 🗑 to remove a rule.")

    for j, rule in enumerate(excl_selected):
        row_c1, row_c2 = st.columns([0.9, 0.1], gap="small")

        with row_c1:
            txt = st.text_area(
                f"excl_txt_input_{j}",
                value=rule,
                key=f"excl_txt_key_{j}",
                height=64,
                label_visibility="collapsed",
            )

        with row_c2:
            delete_clicked = st.button("🗑", key=f"excl_del_{j}", help="Remove this exclusion rule")
        if not delete_clicked and txt.strip():
            edited_excl.append(txt.strip())

st.markdown("---")

# -------- custom add row --------
st.subheader("Add custom criteria")

add_left, add_right = st.columns(2)

with add_left:
    st.caption("Custom inclusion")
    custom_incl_txt = st.text_input(
        "custom_incl_txt",
        value="",
        key="custom_incl_txt_key",
        placeholder="Evaluates at least one approved algorithm",
        label_visibility="collapsed",
    )

    if st.button("Add inclusion", key="btn_add_incl_custom", use_container_width=True):
        cleaned = _shorten_rule(custom_incl_txt.strip())
        if cleaned:
            edited_incl.append(cleaned)
            # immediately push to session
            st.session_state["criteria"]["include"] = edited_incl

with add_right:
    st.caption("Custom exclusion")
    custom_excl_txt = st.text_input(
        "custom_excl_txt",
        value="",
        key="custom_excl_txt_key",
        placeholder="No algorithmic content or performance evidence",
        label_visibility="collapsed",
    )
    if st.button("Add exclusion", key="btn_add_excl_custom", use_container_width=True):
        cleaned = _shorten_rule(custom_excl_txt.strip())
        if cleaned:
            edited_excl.append(cleaned)
            st.session_state["criteria"]["exclude"] = edited_excl

# after possible add buttons fired, make sure we reflect the longer of session vs current
if "include" in st.session_state["criteria"]:
    sess_incl = st.session_state["criteria"].get("include", [])
    if len(sess_incl) > len(edited_incl):
        edited_incl = sess_incl

if "exclude" in st.session_state["criteria"]:
    sess_excl = st.session_state["criteria"].get("exclude", [])
    if len(sess_excl) > len(edited_excl):
        edited_excl = sess_excl

# enforce minimum for export (we don't visually pad, just for saving/export)
final_incl = ensure_minimum(edited_incl, minimum=5, fallback_sentence="Relevant to the defined technical scope")
final_excl = ensure_minimum(edited_excl, minimum=5, fallback_sentence="Outside the defined technical scope")

# -------- save + export --------
bottom_left, bottom_right = st.columns([0.4, 0.6])
with bottom_left:
    if st.button("💾 Save criteria to session", use_container_width=True):
        st.session_state["criteria"] = {
            "include": final_incl,
            "exclude": final_excl,
            "year_from": int(year_from),
            "year_to": int(year_to),
        }
        st.success("Saved criteria to session.")

with bottom_right:
    st.caption("Saved criteria (JSON / Markdown downloads below).")

bundle = {
    "topic": topic,
    "picoc": picoc,
    "sources": sources,
    "criteria": {
        "include": final_incl,
        "exclude": final_excl,
        "year_from": int(year_from),
        "year_to": int(year_to),
    },
}

st.markdown("### Download criteria (JSON)")
st.download_button(
    "⬇️ Download criteria.json",
    data=json.dumps(bundle, ensure_ascii=False, indent=2),
    file_name="slr_criteria.json",
    mime="application/json",
    use_container_width=True,
)

md_lines = ["# Inclusion and Exclusion Criteria", ""]
md_lines.append("## Inclusion")
for r in final_incl:
    md_lines.append(f"- {r}")
md_lines.append("")
md_lines.append("## Exclusion")
for r in final_excl:
    md_lines.append(f"- {r}")
md_lines.append("")
md_lines.append("## Years")
md_lines.append(f"- {year_from}–{year_to}")

# st.markdown("### Download criteria (Markdown)")
# st.download_button(
#     "⬇️ Download criteria.md",
#     data="\n".join(md_lines),
#     file_name="slr_criteria.md",
#     mime="text/markdown",
#     use_container_width=True,
# )

st.info("Next planning step: **Step 5 – Quality assessment checklist**.")
