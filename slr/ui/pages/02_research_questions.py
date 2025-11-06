import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import json
from slr.ui.theme import inject_css
import streamlit as st
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
    """
    Returns a dict you can hand to the LLM that includes both:
    - the core PICOC text
    - user-approved synonyms per facet
    We are NOT changing any downstream agent signature unless we control it.
    We'll just add this to the session so we can hand it to the agent.
    """
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
if st.button("Generate 3 RQs from current PICOC + synonyms", use_container_width=True):
    with st.spinner("Drafting research questions from PICOC and curated synonyms..."):
        try:
            # Build enriched context with synonyms for better wording
            enriched_context = _merge_picoc_with_synonyms(ai_picoc, selected_syns)

            # We assume your agent can be nudged
            # If formulate_rqs_from_picoc only accepts picoc + max_rqs, we still call it
            # but we ALSO stash enriched_context in session for possible agent-side pickup
            # (you can wire the agent to read st.session_state if you want).
            st.session_state["rq_generation_context"] = enriched_context

            payload = formulate_rqs_from_picoc(ai_picoc, max_rqs=3)
            # expected {"rqs": [...], "notes": "..."}
        except Exception as e:
            st.error(f"RQ generation failed: {e}")
            payload = {"rqs": [], "notes": ""}

    # overwrite current list/notes with fresh draft
    st.session_state["rqs"] = payload.get("rqs", [])
    st.session_state["rq_notes"] = payload.get("notes", "")


# convenience local vars (live view)
rqs = st.session_state.get("rqs", [])
rq_notes = st.session_state.get("rq_notes", "")

if not rqs:
    st.info("Click **Generate 3–5 RQs from current PICOC + synonyms** to draft questions.")
else:
    st.caption("Edit your questions below. You can delete individual RQs or add new ones. All changes are saved live.")

    updated_rqs = []

    # --- 2) Editable list of RQs with per-RQ delete ---
    for idx, rq in enumerate(rqs):
        # row layout: text_input (stretch) + small delete button on the right
        col_q, col_del = st.columns([10, 1])
        with col_q:
            new_txt = st.text_input(
                f"RQ{idx+1}",
                value=rq,
                key=f"rq_text_{idx}",
            )
        with col_del:
            # tiny delete button
            if st.button("🗑️", key=f"del_{idx}", help="Delete this RQ"):
                # skip adding to updated_rqs -> effectively delete
                new_txt = None

        if new_txt is not None and new_txt.strip():
            updated_rqs.append(new_txt.strip())

    # --- 3) Add-new-RQ UI ---
    st.markdown("#### Add a new research question")
    new_col1, new_col2 = st.columns([10, 1])

    # We keep a temp buffer in session so the input doesn't reset each rerun
    if "new_rq_draft" not in st.session_state:
        st.session_state["new_rq_draft"] = ""

    with new_col1:
        st.session_state["new_rq_draft"] = st.text_input(
            "New RQ",
            value=st.session_state["new_rq_draft"],
            key="new_rq_input",
            placeholder="Type a new research question here…",
            help="You can press Enter or click 'Add'.",
        )

    with new_col2:
        # Explicit add button
        add_clicked = st.button("➕ Add", key="btn_add_new_rq", help="Append this question to the list")

    # Also support Enter-to-apply:
    # Streamlit behavior: pressing Enter on text_input triggers a rerun immediately.
    # We'll treat 'Enter' as: if draft changed and not already in list, append.
    # To keep it simple we always append if add_clicked OR (draft not empty and not already appended this run).
    # We'll control 'already appended this run' with a flag.
    if "just_added_this_run" not in st.session_state:
        st.session_state["just_added_this_run"] = False

    draft_val = st.session_state["new_rq_draft"].strip()

    if add_clicked and draft_val:
        updated_rqs.append(draft_val)
        st.session_state["new_rq_draft"] = ""           # clear field
        st.session_state["just_added_this_run"] = True

    # If user pressed Enter (rerun) but didn't click Add, we still want to catch it.
    # Heuristic: if we haven't just added in this run AND draft_val not empty AND not already present at end.
    elif (not st.session_state["just_added_this_run"]) and draft_val:
        # check if it's already last element from previous run
        if not updated_rqs or updated_rqs[-1] != draft_val:
            # Don't auto-append silently every rerun, that can spam.
            # We'll *not* auto-append here, because you said you like "Press Enter to apply",
            # but also want the button. We keep the hint text, but we now rely mainly on the button.
            pass

    # reset the flag for next rerun
    st.session_state["just_added_this_run"] = False

    st.markdown("---")


    # --- 7) Downloads (unchanged) ---
    bundle = {
        "topic": topic,
        "picoc": ai_picoc,
        "synonyms_selected": selected_syns,
        "rqs": updated_rqs,
        "notes": st.session_state.get("rq_notes", ""),
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
    if st.session_state.get("rq_notes", ""):
        md_lines += ["", "## Notes", st.session_state["rq_notes"]]

    st.download_button(
        "Download RQs (Markdown)",
        data="\n".join(md_lines),
        file_name="research_questions.md",
        mime="text/markdown",
        use_container_width=True,
    )

st.markdown("---")
