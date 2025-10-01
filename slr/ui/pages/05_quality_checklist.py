import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import json
import streamlit as st

# --------------- Page setup ---------------
st.set_page_config(page_title="Planning → Step 5: Quality Checklist", layout="wide")
st.markdown(
    "<h2 style='margin-top:25px;'>🧪 Planning • Step 5: Define Quality Assessment Checklist</h2>",
    unsafe_allow_html=True,
)

# Compact row styling
st.markdown("""
<style>
div[data-testid="stHorizontalBlock"] > div { padding-right:.35rem !important; }
div[data-baseweb="input"] input { padding-top:6px; padding-bottom:6px; }
</style>
""", unsafe_allow_html=True)

topic   = st.session_state.get("topic", "")
picoc   = st.session_state.get("ai_picoc", {})
criteria = st.session_state.get("criteria", {})
sources  = st.session_state.get("sources", {})

if topic:
    st.caption(f"Current topic: **{topic}**")
st.markdown("---")

st.write(
    "Define a **Quality Assessment Checklist (QAC)** for evaluating candidate studies during the *study selection & refinement* stage. "
    "Choose a scoring scheme, edit questions, set a cut-off, and export the protocol artifact."
)

# --------------- Defaults ---------------
DEFAULT_QS = [
    "The study clearly states its research questions/objectives.",
    "The methodology/design is adequately described for replication.",
    "The dataset/experimental setup is available or sufficiently detailed.",
    "The study compares against appropriate baselines or alternatives.",
    "The reported results include relevant metrics with enough detail.",
    "The study discusses threats to validity or limitations.",
    "The venue suggests peer review or the preprint shows adequate rigor.",
]

# Load / initialize session state
saved = st.session_state.get("quality_checklist", {})
scheme = saved.get("scheme", "Y/N")                # "Y/N" or "Y/P/N"
qs      = saved.get("questions", DEFAULT_QS)
cutoff  = saved.get("cutoff", 4)                   # default cut-off for 7 binary Y/N
weights = saved.get("weights", [1]*len(qs))        # per-question weights (optional, defaults 1)

# --------------- Scoring scheme ---------------
st.subheader("Scoring scheme")
col_s1, col_s2 = st.columns([0.5, 0.5])
with col_s1:
    scheme = st.radio(
        "Select scheme",
        ["Y/N", "Y/P/N"],
        horizontal=True,
        index=0 if scheme == "Y/N" else 1,
        help="Y/N: Yes=1, No=0  •  Y/P/N: Yes=2, Partial=1, No=0"
    )
with col_s2:
    if scheme == "Y/N":
        st.info("**Binary** scoring. Each question: Yes=1, No=0. Suggested cut-off for 7 Qs: 4 or 5.", icon="ℹ️")
    else:
        st.info("**Ternary** scoring. Each question: Yes=2, Partial=1, No=0. Suggested cut-off for 7 Qs: 8–10.", icon="ℹ️")

# --------------- Edit questions ---------------
st.subheader("Checklist questions")
st.caption("Edit existing questions or add your own. (Weights are optional, default 1 each.)")

new_qs, new_weights = [], []
for i, q in enumerate(qs):
    c1, c2, c3 = st.columns([0.06, 0.78, 0.16], gap="small")
    with c1:
        keep = st.checkbox(" ", value=True, key=f"qc_keep_{i}")  # remove unchecked items
    with c2:
        txt = st.text_input(f"qc_q_{i}", value=q, label_visibility="collapsed")
    with c3:
        w = st.number_input(
    "Weight", key=f"qc_w_{i}",
    value=float(weights[i] if i < len(weights) else 1),
    min_value=0.0, step=0.5
)

    if keep and txt.strip():
        new_qs.append(txt.strip())
        new_weights.append(w)

# Add custom question
cadd = st.columns([0.84, 0.16], gap="small")
with cadd[0]:
    custom_q = st.text_input("Add custom question", value="", placeholder="e.g., The code or artifacts are available (repo/DOI).")
with cadd[1]:
    if st.button("➕ Add Q"):
        if custom_q.strip():
            new_qs.append(custom_q.strip())
            new_weights.append(1.0)

# Ensure at least 5 questions (common practice)
if len(new_qs) < 5:
    st.warning(f"Checklist has {len(new_qs)} questions (<5). Consider adding more for robust assessment.")

# --------------- Cut-off suggestion ---------------
max_per_q = 1 if scheme == "Y/N" else 2
max_total = int(round(sum(new_weights) * max_per_q))
cutoff = st.number_input(
    "Minimum total score to include a study",
    value=int(cutoff if cutoff is not None else int(round(len(new_qs) * max_per_q * 0.6))),
    min_value=0, max_value=max_total, step=1,
    help=f"Rule of thumb: ~60% of max score. Current max: {max_total}."
)


# --------------- Save & Export ---------------
if st.button("Save checklist to session", use_container_width=True):
    st.session_state["quality_checklist"] = {
        "scheme": scheme,                 # "Y/N" or "Y/P/N"
        "questions": new_qs,              # list[str]
        "weights": new_weights,           # list[float]
        "cutoff": int(cutoff),
        "notes": "Planning artifact: to be used during study quality scoring.",
    }
    st.success("Saved quality checklist to session.")

st.subheader("Current snapshot")
st.write(f"**Scheme:** {scheme}")
st.write(f"**Questions ({len(new_qs)}):**")
st.markdown("\n".join([f"- (w={new_weights[i]:g}) {q}" for i, q in enumerate(new_qs)]) or "_None_")
st.write(f"**Cut-off:** {cutoff}  •  **Max per question:** {max_per_q}")

bundle = {
    "topic": topic,
    "picoc": picoc,
    "sources": sources,
    "criteria": criteria,
    "quality_checklist": {
        "scheme": scheme,
        "questions": new_qs,
        "weights": new_weights,
        "cutoff": int(cutoff),
    },
}

st.download_button(
    "Download quality checklist (JSON)",
    data=json.dumps(bundle, ensure_ascii=False, indent=2),
    file_name="slr_quality_checklist.json",
    mime="application/json",
    use_container_width=True,
)

# Markdown export
md = ["# Quality Assessment Checklist", ""]
md.append(f"- Scheme: **{scheme}**  (Y/N: Yes=1, No=0;  Y/P/N: Yes=2, Partial=1, No=0)")
md.append(f"- Questions ({len(new_qs)}):")
for i, q in enumerate(new_qs, 1):
    md.append(f"  {i}. {q} (w={new_weights[i-1]:g})")
md.append(f"- Cut-off: **{cutoff}**")
st.download_button(
    "Download quality checklist (Markdown)",
    data="\n".join(md),
    file_name="slr_quality_checklist.md",
    mime="text/markdown",
    use_container_width=True,
)

st.info(
    "This completes **Planning • Step 5: Quality checklist**. "
    "Next in planning is **Step 6: Design the data extraction form** (what fields you’ll extract from each study)."
)
