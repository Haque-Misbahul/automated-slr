import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import json
import streamlit as st

# ---------------- Page setup ----------------
st.set_page_config(page_title="Planning → Step 3: Select Sources", layout="wide")
st.markdown(
    "<h2 style='margin-top:25px;'>🗂️ Planning • Step 3: Select Digital Library Sources</h2>",
    unsafe_allow_html=True,
)

st.write(
    "In the planning phase we must **declare where we will search**. "
    "This protocol uses **arXiv** as the primary source for CS research, with category filters for reproducibility."
)

# Optional compact CSS (uses your existing styles if present)
for css_name in ("styles.css", "style.css"):
    css_path = os.path.join(os.path.dirname(__file__), "..", css_name)
    css_path = os.path.abspath(css_path)
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
        break

# ---------------- arXiv categories (CS) ----------------
ARXIV_CS = [
    ("cs.AI", "Artificial Intelligence"),
    ("cs.CL", "Computation and Language (NLP)"),
    ("cs.CV", "Computer Vision and Pattern Recognition"),
    ("cs.LG", "Machine Learning"),
    ("cs.NE", "Neural and Evolutionary Computing"),
    ("cs.SE", "Software Engineering"),
    ("cs.DS", "Data Structures and Algorithms"),
    ("cs.PL", "Programming Languages"),
    ("cs.OS", "Operating Systems"),
    ("cs.DC", "Distributed, Parallel, and Cluster Computing"),
    ("cs.DB", "Databases"),
    ("cs.IR", "Information Retrieval"),
    ("cs.CR", "Cryptography and Security"),
    ("cs.HC", "Human-Computer Interaction"),
    ("cs.SI", "Social and Information Networks"),
    ("cs.RO", "Robotics"),
    ("cs.CY", "Computers and Society"),
    ("cs.GL", "General Literature"),
]

code_to_label = {c:l for c,l in ARXIV_CS}

# ---------------- Load prior selection ----------------
saved = st.session_state.get("sources", {})
saved_cats = saved.get("categories", []) if saved.get("provider") == "arXiv" else []

# ---------------- Selections ----------------
st.subheader("Choose arXiv CS categories")
all_codes = [c for c, _ in ARXIV_CS]

# presets
preset_cols = st.columns(3)
with preset_cols[0]:
    if st.button("SE focus (cs.SE, cs.PL, cs.DC, cs.OS, cs.DB)", use_container_width=True):
        saved_cats = ["cs.SE", "cs.PL", "cs.DC", "cs.OS", "cs.DB"]
with preset_cols[1]:
    if st.button("ML/AI focus (cs.LG, cs.AI, cs.CL, cs.CV, cs.NE)", use_container_width=True):
        saved_cats = ["cs.LG", "cs.AI", "cs.CL", "cs.CV", "cs.NE"]
with preset_cols[2]:
    if st.button("Algorithms/Theory (cs.DS, cs.CC*)", use_container_width=True):
        # cs.CC (computational complexity) is not in the list; we keep DS only for now.
        saved_cats = ["cs.DS"]

selected = st.multiselect(
    "arXiv categories",
    options=all_codes,
    default=saved_cats or ["cs.SE", "cs.LG"],  # sensible default
    format_func=lambda c: f"{c} — {code_to_label.get(c, c)}",
    help="Pick one or more categories relevant to your SLR scope.",
)

# optional notes / justification (good for protocol)
st.subheader("Rationale / notes (optional)")
notes = st.text_area(
    "Why arXiv and these categories?",
    value=st.session_state.get("sources_notes", ""),
    height=100,
    placeholder=(
        "e.g., arXiv provides broad CS coverage and rapid access to preprints; "
        "we constrain to cs.SE and cs.LG due to our scope on software engineering with ML-based methods."
    ),
)

# ---------------- Save to session ----------------
if st.button("Save selection", use_container_width=True):
    st.session_state["sources"] = {
        "provider": "arXiv",
        "categories": selected,
    }
    st.session_state["sources_notes"] = notes
    st.success("Saved sources to session.")

# ---------------- Current summary ----------------
curr = st.session_state.get("sources", {})
if curr:
    st.markdown("### Current selection")
    cats = curr.get("categories", [])
    if cats:
        st.write(", ".join([f"{c} — {code_to_label.get(c, c)}" for c in cats]))
    else:
        st.write("_No categories selected._")

# ---------------- Export for protocol ----------------
bundle = {
    "topic": st.session_state.get("topic", ""),
    "picoc": st.session_state.get("ai_picoc", {}),
    "sources": {
        "provider": "arXiv",
        "categories": selected,
        "notes": notes,
    },
}
st.download_button(
    "Download sources (JSON)",
    data=json.dumps(bundle, ensure_ascii=False, indent=2),
    file_name="slr_sources_arxiv.json",
    mime="application/json",
    use_container_width=True,
)

st.info(
    "This finishes **Planning • Step 3: Select sources**. "
    "Next in planning is **Step 4: Inclusion/Exclusion criteria** and **Step 5: Quality checklist**."
)
