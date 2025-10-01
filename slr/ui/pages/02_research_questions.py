import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import json
import streamlit as st
from slr.agents.formulate_rq import formulate_rqs_from_picoc

# ---------- Page setup ----------
st.set_page_config(page_title="Planning → Step 2: Research Questions", layout="wide")
st.markdown(
    "<h2 style='margin-top:25px;'>📝 Planning • Step 2: Formulate Research Questions (from PICOC)</h2>",
    unsafe_allow_html=True,
)

# ---------- Get PICOC from Step 1 ----------
topic   = st.session_state.get("topic", "")
ai_picoc = st.session_state.get("ai_picoc")
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

# ---------- Generate / edit RQs ----------
st.subheader("Draft Research Questions")

if st.button("Generate 5–7 RQs from current PICOC", use_container_width=True):
    with st.spinner("Drafting research questions from PICOC..."):
        try:
            payload = formulate_rqs_from_picoc(ai_picoc, max_rqs=7)
        except Exception as e:
            st.error(f"RQ generation failed: {e}")
            payload = {"rqs": [], "notes": ""}
    st.session_state["rqs"] = payload.get("rqs", [])
    st.session_state["rq_notes"] = payload.get("notes", "")

rqs = st.session_state.get("rqs", [])
rq_notes = st.session_state.get("rq_notes", "")

if not rqs:
    st.info("Click **Generate RQs from current PICOC** to draft questions.")
else:
    st.caption("Edit your questions below. Changes are saved live in session.")
    new_rqs = []
    for i, rq in enumerate(rqs):
        txt = st.text_input(f"RQ{i+1}", value=rq, key=f"rq_{i}")
        if txt.strip():
            new_rqs.append(txt.strip())

    c3, c4, c5 = st.columns(3)
    with c3:
        if st.button("➕ Add empty RQ"):
            new_rqs.append("")
    with c4:
        if st.button("🧹 Clear all RQs"):
            new_rqs = []

    st.session_state["rqs"] = new_rqs

    st.text_area("Notes (optional)", value=rq_notes, key="rq_notes", height=80)

    # Downloads
    bundle = {
        "topic": topic,
        "picoc": ai_picoc,
        "rqs": new_rqs,
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
    for i, q in enumerate(new_rqs, 1):
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
