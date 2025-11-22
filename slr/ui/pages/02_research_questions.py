# slr/ui/pages/02_Research_Questions.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import json
import streamlit as st
from slr.ui.theme import inject_css
from slr.agents.formulate_rq import formulate_rqs_from_picoc

# ---------- Page setup ----------
st.set_page_config(page_title="Planning → Step 2: Research Questions", layout="wide")
inject_css()
st.markdown(
    "<h2 style='margin-top:25px;'>Planning • Step 2: Formulate Research Questions (from PICOC)</h2>",
    unsafe_allow_html=True,
)

# ---------- Get PICOC + synonyms from Step 1 ----------
topic = st.session_state.get("topic", "")
ai_picoc = st.session_state.get("ai_picoc")
selected_syns = st.session_state.get("selected_synonyms", {})  # dict with Population/Intervention/... lists

if not ai_picoc:
    st.warning("No PICOC found in session. Please go to **Step 1** and generate PICOC first.")
    st.stop()

# Show current PICOC (read-only here)
st.subheader("PICOC in session")
c1, c2 = st.columns(2)
with c1:
    st.write(f"**Population:** {ai_picoc.get('population','')}")
    st.write(f"**Intervention:** {ai_picoc.get('intervention','')}")
    st.write(f"**Comparison:** {ai_picoc.get('comparison','')}")
with c2:
    st.write(f"**Outcome:** {ai_picoc.get('outcome','')}")
    st.write(f"**Context:** {ai_picoc.get('context','')}")

st.markdown("---")

# ---------- Helper: build enriched context for the RQ generator ----------
def _merge_picoc_with_synonyms(picoc_dict, syn_dict):
    return {
        "picoc": {
            "population": picoc_dict.get("population", ""),
            "intervention": picoc_dict.get("intervention", ""),
            "comparison": picoc_dict.get("comparison", ""),
            "outcome": picoc_dict.get("outcome", ""),
            "context": picoc_dict.get("context", ""),
        },
        "synonyms": {
            "Population":   syn_dict.get("Population", []),
            "Intervention": syn_dict.get("Intervention", []),
            "Comparison":   syn_dict.get("Comparison", []),
            "Outcome":      syn_dict.get("Outcome", []),
            "Context":      syn_dict.get("Context", []),
        },
        "topic": topic,
    }

# ---------- Generate / edit RQs ----------
st.subheader("Draft Research Questions")

# init session keys if first load
if "rqs" not in st.session_state:
    st.session_state["rqs"] = []  # list[str]
if "rq_notes" not in st.session_state:
    st.session_state["rq_notes"] = ""

# --- 1) Generate RQs button (AI) ---
c1, c_mid, c3 = st.columns([1, 3, 1])

with c_mid:
    gen_rq_clicked = st.button(
        "Generate 3 RQs from current PICOC + synonyms",
        use_container_width=True,
        help="Click to generate 3 draft research questions from the current PICOC and synonyms",
    )

if gen_rq_clicked:
    with st.spinner("Drafting research questions from PICOC and curated synonyms..."):
        try:
            enriched_context = _merge_picoc_with_synonyms(ai_picoc, selected_syns)
            st.session_state["rq_generation_context"] = enriched_context
            payload = formulate_rqs_from_picoc(ai_picoc, max_rqs=3)  # 3 only
        except Exception as e:
            st.error(f"RQ generation failed: {e}")
            payload = {"rqs": [], "notes": ""}

    st.session_state["rqs"] = payload.get("rqs", [])
    st.session_state["rq_notes"] = payload.get("notes", "")



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


# convenience local vars (live view)
rqs = st.session_state.get("rqs", [])
rq_notes = st.session_state.get("rq_notes", "")

if not rqs:
    st.info("Click **Generate 3 RQs from current PICOC + synonyms** to draft questions.")
else:
    st.caption("Edit your questions below. You can delete individual RQs or add new ones. All changes are saved live.")

    updated_rqs = []

    # --- 2) Editable list of RQs with per-RQ delete (wrapped, aligned) ---
    for idx, rq in enumerate(rqs):
        col_label, col_input, col_del = st.columns([1, 10, 1])

        with col_label:
            st.markdown(f"**RQ{idx+1}**")

        with col_input:
            new_txt = st.text_area(
                label=f"RQ {idx+1} text",
                value=rq,
                key=f"rq_text_{idx}",
                height=64,                    # adjust height as you like
                label_visibility="collapsed", # keep UI clean; we show RQ# at left
            )

        with col_del:
            if st.button("🗑️", key=f"del_{idx}", help="Delete this RQ"):
                new_txt = None

        if new_txt is not None and new_txt.strip():
            updated_rqs.append(new_txt.strip())

    # --- 3) Add-new-RQ UI (aligned on one row) ---
    st.markdown("#### Add a new research question")
    col_label, new_col1, new_col2 = st.columns([1, 10, 1])

    if "new_rq_draft" not in st.session_state:
        st.session_state["new_rq_draft"] = ""

    with col_label:
        st.markdown("**New RQ**")

    with new_col1:
        st.session_state["new_rq_draft"] = st.text_input(
            "New RQ",
            value=st.session_state["new_rq_draft"],
            key="new_rq_input",
            placeholder="Type a new research question here…",
            help="You can press Enter or click 'Add'.",
            label_visibility="collapsed",
        )

    with new_col2:
        add_clicked = st.button("➕ Add", key="btn_add_new_rq", help="Append this question to the list")

    # enter/add handling
    if "just_added_this_run" not in st.session_state:
        st.session_state["just_added_this_run"] = False

    draft_val = st.session_state["new_rq_draft"].strip()

    if add_clicked and draft_val:
        updated_rqs.append(draft_val)
        st.session_state["new_rq_draft"] = ""   # clear
        st.session_state["just_added_this_run"] = True
    elif (not st.session_state["just_added_this_run"]) and draft_val:
        # do nothing (avoid duplicate auto-append on reruns)
        pass
    st.session_state["just_added_this_run"] = False

    # --- persist back to session (IMPORTANT) ---
    st.session_state["rqs"] = updated_rqs

    st.markdown("---")

    # --- 4) Downloads ---
    bundle = {
        "topic": topic,
        "picoc": ai_picoc,
        "synonyms_selected": selected_syns,
        "rqs": updated_rqs,
        "notes": rq_notes,
    }

    st.download_button(
        "Download RQs (JSON)",
        data=json.dumps(bundle, ensure_ascii=False, indent=2),
        file_name="research_questions.json",
        mime="application/json",
        use_container_width=True,
    )

    md_lines = ["# Research Questions", ""]
    for i, q in enumerate(updated_rqs, 1):
        md_lines.append(f"- **RQ{i}.** {q}")
    if rq_notes:
        md_lines += ["", "## Notes", rq_notes]

    st.download_button(
        "Download RQs (Markdown)",
        data="\n".join(md_lines),
        file_name="research_questions.md",
        mime="text/markdown",
        use_container_width=True,
    )

st.markdown("---")
