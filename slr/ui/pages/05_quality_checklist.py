import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import json
import streamlit as st
from slr.ui.theme import inject_css

# --------------- Page setup ---------------
st.set_page_config(page_title="Planning → Step 5: Quality Checklist", layout="wide")
inject_css()
st.markdown(
    "<h2 style='margin-top:25px;'>Planning • Step 5: Define Quality Assessment Checklist</h2>",
    unsafe_allow_html=True,
)

# Compact row styling + minor spacing
st.markdown("""
<style>
div[data-testid="stHorizontalBlock"] > div { padding-right:.35rem !important; }
div[data-baseweb="input"] input { padding-top:6px; padding-bottom:6px; }
/* tighten row height */
label[data-baseweb="checkbox"] { margin-bottom: 0px !important; }
/* right-align the weight radio a bit */
.qc-weight-col { display:flex; justify-content:flex-end; align-items:center; }
.qc-weight-col > div { margin-bottom:0 !important; }
/* align Add Q button with textbox */
.qc-addq-align { display:flex; align-items:center; height:100%; }
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
    "This page uses a fixed **Yes / Partial / No** scoring scheme (**Yes=1, Partial=0.5, No=0**). "
    "Edit questions, set per-question weights, choose a minimum total score, and export the artifact."
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

# Load / initialize session state (working copy you can edit live)
saved = st.session_state.get("quality_checklist", {})

# Scheme fixed to Y/P/N (logic: Yes=1, Partial=0.5, No=0)
scheme = "Y/P/N"

if "qc_qs" not in st.session_state:
    st.session_state["qc_qs"] = saved.get("questions", DEFAULT_QS).copy()
if "qc_ws" not in st.session_state:
    base_ws = saved.get("weights", [1.0] * len(st.session_state["qc_qs"]))
    if len(base_ws) != len(st.session_state["qc_qs"]):
        base_ws = (base_ws + [1.0] * len(st.session_state["qc_qs"]))[:len(st.session_state["qc_qs"])]
    st.session_state["qc_ws"] = [float(w) for w in base_ws]

# --------------- Scoring scheme (fixed) ---------------
st.subheader("Scoring scheme")
st.info("**Yes / Partial / No** (fixed): **Yes=1, Partial=0.5, No=0**. Suggested cut-off for 7 Qs (w=1): **4–5**.", icon="ℹ️")

# --------------- Editable list (aligned: checkbox • question • weight radio) ---------------
st.subheader("Checklist questions")
st.caption("Edit existing questions or add your own. Weights use a compact **1 / 0.5 / 0** radio on the right.")

qs_work = st.session_state["qc_qs"]
ws_work = st.session_state["qc_ws"]

# Header row for alignment (no repeated 'Weight' text on every line)
h1, h2, h3 = st.columns([0.05, 0.72, 0.23], gap="small")
with h1:
    st.markdown("**Keep**")
with h2:
    st.markdown("**Question**")
with h3:
    st.markdown("**Weight (1 / 0.5 / 0)**")

new_qs, new_ws = [], []
for i, q in enumerate(qs_work):
    c1, c2, c3 = st.columns([0.05, 0.72, 0.23], gap="small")
    with c1:
        keep = st.checkbox(" ", value=True, key=f"qc_keep_{i}")
    with c2:
        txt = st.text_input(f"qc_q_{i}", value=q, label_visibility="collapsed")
    with c3:
        with st.container():
            st.markdown('<div class="qc-weight-col">', unsafe_allow_html=True)
            w_choice = st.radio(
                f"qc_w_{i}",
                options=[1.0, 0.5, 0.0],
                index={1.0:0, 0.5:1, 0.0:2}.get(float(ws_work[i]) if i < len(ws_work) else 1.0, 0),
                horizontal=True,
                label_visibility="collapsed",
                key=f"qc_w_radio_{i}",
            )
            st.markdown('</div>', unsafe_allow_html=True)

    if keep and txt.strip():
        new_qs.append(txt.strip())
        new_ws.append(float(w_choice))

# Persist the edited lists back for next rerun
st.session_state["qc_qs"] = new_qs
st.session_state["qc_ws"] = new_ws

# --------------- Add custom question (below list; aligned button) ---------------
add_mid, add_r = st.columns([0.77, 0.23], gap="small")
with add_mid:
    custom_q = st.text_input(
        "Add custom question",
        value="",
        placeholder="e.g., The code or artifacts are available (repo/DOI).",
    )
with add_r:
    st.markdown('<div class="qc-addq-align">', unsafe_allow_html=True)
    add_clicked = st.button("➕ Add Q")
    st.markdown('</div>', unsafe_allow_html=True)

if add_clicked and custom_q.strip():
    st.session_state["qc_qs"].append(custom_q.strip())
    st.session_state["qc_ws"].append(1.0)  # default weight for new item
    st.rerun()

# Ensure at least 5 questions (common practice)
if len(new_qs) < 5:
    st.warning(f"Checklist has {len(new_qs)} questions (<5). Consider adding more for robust assessment.")

# --------------- Cut-off + totals (uses fixed Y/P/N logic 1 / 0.5 / 0) ---------------
max_per_q = 1  # Yes=1, Partial=0.5, No=0
total_weight = float(sum(new_ws))
max_total = int(round(total_weight * max_per_q))
default_cut = saved.get("cutoff", int(round(total_weight * max_per_q * 0.6)))  # ~60% rule

cut_l, cut_r = st.columns([0.5, 0.5], gap="small")
with cut_l:
    cutoff = st.number_input(
        "Minimum total score to include a study",
        value=int(default_cut),
        min_value=0, max_value=max_total, step=1,
        help=f"Rule of thumb: ~60% of max score. Current max: {max_total}.",
    )
with cut_r:
    st.markdown(
        f"**Total weight:** {total_weight:g}  &nbsp;•&nbsp; "
        f"**Max possible score (all Yes):** {max_total}",
    )

# --------------- Save & Export ---------------
if st.button("Save checklist to session", use_container_width=True):
    st.session_state["quality_checklist"] = {
        "scheme": "Y/P/N",             # fixed
        "questions": new_qs,           # list[str]
        "weights": new_ws,             # list[float]
        "cutoff": int(cutoff),
        "notes": "Planning artifact: to be used during study quality scoring.",
    }
    st.success("Saved quality checklist to session.")

st.subheader("Current snapshot")
st.write(f"**Scheme:** Y/P/N  (Yes=1, Partial=0.5, No=0)")
st.write(f"**Questions ({len(new_qs)}):**")
st.markdown("\n".join([f"- (w={new_ws[i]:g}) {q}" for i, q in enumerate(new_qs)]) or "_None_")
st.write(f"**Cut-off:** {cutoff}  •  **Max per question:** {max_per_q}  •  **Total weight:** {total_weight:g}  •  **Max score:** {max_total}")

bundle = {
    "topic": topic,
    "picoc": picoc,
    "sources": sources,
    "criteria": criteria,
    "quality_checklist": {
        "scheme": "Y/P/N",
        "questions": new_qs,
        "weights": new_ws,
        "cutoff": int(cutoff),
        "total_weight": total_weight,
        "max_score": max_total,
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
md.append(f"- Scheme: **Y/P/N**  (Yes=1, Partial=0.5, No=0)")
md.append(f"- Questions ({len(new_qs)}):")
for i, q in enumerate(new_qs, 1):
    md.append(f"  {i}. {q} (w={new_ws[i-1]:g})")
md.append(f"- Total weight: **{total_weight:g}**")
md.append(f"- Max possible score (all Yes): **{max_total}**")
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
    "Next in planning is **Step 6: Design the data extraction form**."
)
