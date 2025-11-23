# slr/ui/pages/p05_quality_checklist.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import json
import streamlit as st
from slr.ui.theme import inject_css
from slr.agents.quality_checklist import generate_quality_checklist

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

# ------- session context -------
topic    = st.session_state.get("topic", "")
picoc    = st.session_state.get("ai_picoc", {})
criteria = st.session_state.get("criteria", {})
sources  = st.session_state.get("sources", {})

if topic:
    st.caption(f"Current topic: **{topic}**")
st.markdown("---")

st.write(
    "Define a **Quality Assessment Checklist (QAC)** for evaluating candidate studies during the "
    "*study selection & refinement* stage. "
    "The checklist uses a fixed **Yes / Partial / No** scheme (**Yes=1, Partial=0.5, No=0**). "
    "You can **generate a short checklist with AI from your search keywords**, then edit and export it."
)

# ------- session storage for this page -------
if "quality_checklist" not in st.session_state:
    st.session_state["quality_checklist"] = {
        "questions": [],
        "weights": [],
        "cutoff": None,
    }

saved = st.session_state["quality_checklist"]

if "qc_qs" not in st.session_state:
    st.session_state["qc_qs"] = list(saved.get("questions", []))

if "qc_ws" not in st.session_state:
    base_ws = saved.get("weights", [])
    if len(base_ws) != len(st.session_state["qc_qs"]):
        base_ws = [1.0] * len(st.session_state["qc_qs"])
    st.session_state["qc_ws"] = [float(w) for w in base_ws]

qs_work = st.session_state["qc_qs"]
ws_work = st.session_state["qc_ws"]

# --------------- AI-assisted generation ---------------
st.subheader("AI-assisted quality checklist generation")

# with st.expander("✨ Generate checklist from search keywords (recommended)", expanded=True):
#     default_seed = topic or ""
#     search_keywords = st.text_area(
#         "Search keywords / Boolean query / short description",
#         value=default_seed,
#         placeholder='e.g., "code review" AND "defect detection" AND (tool OR automation)',
#         help="The AI will use this plus your PICOC and screening criteria (Step 4) "
#              "to propose a short quality checklist.",
#     )

#     # Fixed to 5 checklist questions (no slider)
#     st.caption("The AI will generate exactly **5** short, non-redundant questions.")
#     n_questions = 5


# We skip showing the expander; just derive inputs silently
default_seed = topic or ""
search_keywords = default_seed       # use topic as the hidden query
n_questions = 5                      # always generate exactly 5 questions




   # --- Generate quality checklist button (AI) ---
c1, c_mid, c3 = st.columns([1, 3, 1])

with c_mid:
    qc_clicked = st.button(
        "Generate quality checklist",
        use_container_width=True,
        help="Click to generate a short quality checklist from topic, PICOC, criteria, and keywords",
    )

    if qc_clicked:
        if not search_keywords.strip() and not topic:
            st.error("Please provide at least a topic or some search keywords.")
        else:
            try:
                with st.spinner("Generating short quality checklist…"):
                    q_items = generate_quality_checklist(
                        topic=topic or "",
                        picoc=picoc or {},
                        criteria=criteria or {},
                        search_keywords=search_keywords.strip(),
                        min_questions=int(n_questions),
                        max_questions=int(n_questions),
                    )

                new_qs = [item["question"] for item in q_items]
                new_ws = [float(item.get("weight", 1.0)) for item in q_items]

                st.session_state["qc_qs"] = new_qs
                st.session_state["qc_ws"] = new_ws

                st.success(f"Generated {len(new_qs)} questions. Refine them below.")

                # rerun to refresh widgets
                if hasattr(st, "rerun"):
                    st.rerun()
                elif hasattr(st, "experimental_rerun"):
                    st.experimental_rerun()

            except Exception as e:
                st.error(f"Checklist generation failed: {e}")

st.markdown("---")

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

# --------------- Scoring scheme (fixed) ---------------
st.subheader("Scoring scheme")
st.info(
    "**Yes / Partial / No** (fixed): **Yes=1, Partial=0.5, No=0**. "
    "Use the weights to emphasize more critical questions.",
    icon="ℹ️",
)

# --------------- Editable list ---------------
st.subheader("Checklist questions")
st.caption(
    "Edit existing questions or add your own. "
    "Weights use a compact **1 / 0.5 / 0** radio on the right."
)

qs_work = st.session_state["qc_qs"]
ws_work = st.session_state["qc_ws"]

if not qs_work:
    st.info(
        "No checklist questions yet. Use **“Generate quality checklist”** above "
        "or add questions manually below."
    )

# Header row
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
        st.markdown('<div class="qc-weight-col">', unsafe_allow_html=True)
        w_choice = st.radio(
            f"qc_w_{i}",
            options=[1.0, 0.5, 0.0],
            index={1.0: 0, 0.5: 1, 0.0: 2}.get(
                float(ws_work[i]) if i < len(ws_work) else 1.0,
                0,
            ),
            horizontal=True,
            label_visibility="collapsed",
            key=f"qc_w_radio_{i}",
        )
        st.markdown('</div>', unsafe_allow_html=True)

    if keep and txt.strip():
        new_qs.append(txt.strip())
        new_ws.append(float(w_choice))

# Persist edited lists
st.session_state["qc_qs"] = new_qs
st.session_state["qc_ws"] = new_ws

# --------------- Add custom question ---------------
add_mid, add_r = st.columns([0.77, 0.23], gap="small")
with add_mid:
    custom_q = st.text_input(
        "Add custom question",
        value="",
        placeholder="e.g., Clearly reports threats to validity.",
    )
with add_r:
    st.markdown('<div class="qc-addq-align">', unsafe_allow_html=True)
    add_clicked = st.button("➕ Add Q")
    st.markdown('</div>', unsafe_allow_html=True)

if add_clicked and custom_q.strip():
    st.session_state["qc_qs"].append(custom_q.strip())
    st.session_state["qc_ws"].append(1.0)
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

# --------------- Cut-off + totals ---------------
max_per_q = 1  # Yes=1, Partial=0.5, No=0
total_weight = float(sum(new_ws))
max_total = int(round(total_weight * max_per_q))

saved_cut = saved.get("cutoff", None)
if saved_cut is not None:
    default_cut = int(saved_cut)
else:
    default_cut = int(round(total_weight * 0.6)) if max_total > 0 else 0

cut_l, cut_r = st.columns([0.5, 0.5], gap="small")
with cut_l:
    cutoff = st.number_input(
        "Minimum total score to include a study",
        value=default_cut,
        min_value=0,
        max_value=max_total if max_total > 0 else 0,
        step=1,
        help=f"Rule of thumb: ~60% of max score. Current max: {max_total}.",
    )
with cut_r:
    st.markdown(
        f"**Total weight:** {total_weight:g}  &nbsp;•&nbsp; "
        f"**Max possible score (all Yes):** {max_total}",
    )

# --------------- Save & Export ---------------
if st.button("💾 Save checklist to session", use_container_width=True):
    st.session_state["quality_checklist"] = {
        "scheme": "Y/P/N",
        "questions": list(st.session_state["qc_qs"]),
        "weights": list(st.session_state["qc_ws"]),
        "cutoff": int(cutoff),
        "notes": "Planning artifact: to be used during study quality scoring.",
    }
    st.success("Saved quality checklist to session.")

st.subheader("Current snapshot")
st.write("**Scheme:** Y/P/N  (Yes=1, Partial=0.5, No=0)")
st.write(f"**Questions ({len(new_qs)}):**")
st.markdown(
    "\n".join([f"- (w={new_ws[i]:g}) {q}" for i, q in enumerate(new_qs)]) or "_None_"
)
st.write(
    f"**Cut-off:** {cutoff}  •  **Max per question:** {max_per_q}  •  "
    f"**Total weight:** {total_weight:g}  •  **Max score:** {max_total}"
)

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
    "⬇️ Download quality checklist (JSON)",
    data=json.dumps(bundle, ensure_ascii=False, indent=2),
    file_name="slr_quality_checklist.json",
    mime="application/json",
    use_container_width=True,
)

md = ["# Quality Assessment Checklist", ""]
md.append("- Scheme: **Y/P/N**  (Yes=1, Partial=0.5, No=0)")
md.append(f"- Questions ({len(new_qs)}):")
for i, q in enumerate(new_qs, 1):
    md.append(f"  {i}. {q} (w={new_ws[i-1]:g})")
md.append(f"- Total weight: **{total_weight:g}**")
md.append(f"- Max possible score (all Yes): **{max_total}**")
md.append(f"- Cut-off: **{cutoff}**")

st.download_button(
    "⬇️ Download quality checklist (Markdown)",
    data="\n".join(md),
    file_name="slr_quality_checklist.md",
    mime="text/markdown",
    use_container_width=True,
)

st.info(
    "This completes **Planning • Step 5: Quality checklist**. "
    "Next in planning is **Step 6: Design the data extraction form**."
)
