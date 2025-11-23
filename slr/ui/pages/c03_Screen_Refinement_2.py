# slr/ui/pages/c03_quality_assess.py

import sys, os, json, io, csv, time, re
from typing import List, Dict, Any, Tuple, Optional

# allow absolute imports from project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import streamlit as st
from slr.llm.client import LLMClient
from slr.ui.theme import inject_css

st.set_page_config(page_title="Conducting → Step 4: Quality Assessment (AI)", layout="wide")
inject_css()
st.markdown(
    "<h2 style='margin-top:20px;'>🧪 Conducting • Step 4: Quality assessment (AI)</h2>",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 0) Utilities
# -----------------------------------------------------------------------------

def _extract_json_block(txt: str) -> Optional[dict]:
    """
    Best-effort: pull the first JSON object from a model reply that may include
    prose or code fences. Returns dict or None.
    """
    if not txt:
        return None
    # Try fenced ```json ... ```
    m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", txt, flags=re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Try first {...} object
    m = re.search(r"(\{[\s\S]*\})", txt.strip())
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Plain attempt
    try:
        return json.loads(txt)
    except Exception:
        return None

def _rows_to_csv(rows: List[Dict[str, Any]], qcount: int) -> str:
    """
    CSV with per-question answers + total/decision.
    """
    out = io.StringIO()
    w = csv.writer(out)
    base_cols = [
        "id", "title", "published", "category", "link",
        "total_score", "total_score_pct", "decision"
    ]
    ans_cols = [f"Q{i+1}_answer" for i in range(qcount)]
    just_cols = [f"Q{i+1}_why" for i in range(qcount)]
    hdr = base_cols[:5] + ans_cols + just_cols + base_cols[5:]
    w.writerow(hdr)
    for r in rows:
        qa = r.get("qa", {})
        answers = qa.get("answers", []) or []
        whys    = qa.get("justifications", []) or []
        row = [
            r.get("id",""),
            (r.get("title","") or "").replace("\n"," ").strip(),
            r.get("published",""),
            r.get("category",""),
            r.get("link",""),
        ]
        # pad to qcount
        answers = (answers + [""]*qcount)[:qcount]
        whys    = (whys + [""]*qcount)[:qcount]
        row += answers + whys
        row += [
            r.get("total_score",""),
            r.get("total_score_pct",""),
            r.get("decision",""),
        ]
        w.writerow(row)
    return out.getvalue()


# -----------------------------------------------------------------------------
# 1) Load input sets from previous steps
# -----------------------------------------------------------------------------

# Prefer an AI-refined include set if you saved one; otherwise the auto-included.
# (Name-safe: we check a few likely keys.)
candidates: List[Dict[str, Any]] = (
    st.session_state.get("ai_included_rows")
    or st.session_state.get("ai_include")
    or st.session_state.get("screened_rows")
    or []
)

if not candidates:
    st.warning("No included studies found in session. Please finish **Conducting → Screening/Refinement** first.")
    st.stop()

st.success(f"Loaded **{len(candidates)}** included studies to quality-assess.")

# quality checklist from Planning step
qcheck = st.session_state.get("quality_checklist", {})
if not qcheck:
    st.warning("No quality checklist found. Go to **Planning → Step 5 (Quality checklist)** to define one.")
    st.stop()

# Normalize questions: support list[str] or list[dict{text, weight, keep}]
raw_qs = qcheck.get("questions") or []
questions: List[str] = []
weights: List[float] = []

def _coerce_float(x, default=1.0):
    try:
        return float(x)
    except Exception:
        return float(default)

if raw_qs and isinstance(raw_qs[0], dict):
    for q in raw_qs:
        if not q.get("text") or (q.get("keep") is False):
            continue
        questions.append(q["text"])
        weights.append(_coerce_float(q.get("weight", 1.0)))
else:
    for q in raw_qs:
        q = (q or "").strip()
        if q:
            questions.append(q)
            weights.append(1.0)

scheme = (qcheck.get("scheme") or "Y/P/N").upper()  # "Y/N" or "Y/P/N"
# min_total_default = _coerce_float(qcheck.get("min_total", 0.0), 0.0)

if not questions:
    st.warning("Your checklist has no questions marked to keep.")
    st.stop()

max_possible = sum(weights)  # if every answer == 'Y' (score=1)

# -----------------------------------------------------------------------------
# 2) Scoring controls (fixed Y/P/N, adjustable cut-off)
# -----------------------------------------------------------------------------

# Fixed mapping – same as Planning Step 5
y_val = 1.0
p_val = 0.5 if "P" in scheme else 0.0
n_val = 0.0

# Prefer Planning cutoff if available, fall back to any legacy 'min_total'
raw_min = qcheck.get("cutoff", qcheck.get("min_total", 0.0))
min_total_default = _coerce_float(raw_min, 0.0)

st.markdown("### Scoring settings")

# Only one control: minimum total score
cut_off = st.number_input(
    "Minimum total score to include",
    min_value=0.0,
    max_value=max_possible,
    step=0.1,
    value=float(min_total_default if min_total_default > 0 else max_possible * 0.5),
    help=(
        f"Max possible score (all Y): {max_possible:g}. "
        "You can adjust this threshold here if needed."
    ),
)

st.caption(
    f"Scoring uses fixed mapping from Planning: **Y = 1.0, P = 0.5, N = 0.0** "
    f"(scheme: {scheme}).  "
    f"Checklist size: **{len(questions)}**, max possible score: **{max_possible:g}**."
)

# -----------------------------------------------------------------------------
# 3) Model settings
# -----------------------------------------------------------------------------

st.markdown("### AI settings")
mc1, mc2 = st.columns(2)
with mc1:
    temp = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.05)
with mc2:
    model_name = st.text_input("Model (LLMClient)", value="gpt-oss-120b")

# -----------------------------------------------------------------------------
# 4) Prompt template
# -----------------------------------------------------------------------------

SYSTEM = """You are an assistant for systematic literature reviews.
You rate papers against a short quality checklist. Respond STRICTLY with JSON, no commentary.
"""

def build_user_prompt_for_paper(paper: Dict[str, Any]) -> str:
    """
    Build a strict, compact prompt per paper.
    """
    title = paper.get("title","").strip()
    abstract = (paper.get("summary","") or "").strip()
    pub = paper.get("published","")
    cat = paper.get("category","")

    scheme_line = "Allowed answers per question: Y or N." if scheme == "Y/N" else "Allowed answers per question: Y, P (Partial), or N."

    # checklist text with weights
    checklist_lines = []
    for i, (q, w) in enumerate(zip(questions, weights), start=1):
        checklist_lines.append(f"{i}. {q} (weight {w:g})")
    checklist_text = "\n".join(checklist_lines)

    score_map = {"Y": y_val, "P": p_val, "N": n_val}
    if scheme == "Y/N":
        score_map.pop("P", None)
    mapping_text = ", ".join([f"{k}={v:g}" for k, v in score_map.items()])

    # Require strict JSON
    rubric = f"""
Paper:
- Title: {title}
- Abstract: {abstract}
- Published: {pub}
- Category: {cat}

Quality checklist:
{checklist_text}

Scoring:
- {scheme_line}
- Numeric mapping: {mapping_text}
- Total score is sum of (answer_score * weight).
- Also return percentage of max possible ({max_possible:g}).

Output JSON ONLY with the following shape (no extra text):
{{
  "answers": ["Y", "P", "N", ...],          // length = {len(questions)}
  "justifications": ["one sentence per Q", ...],
  "score_per_question": [float, ...],       // after applying mapping * weight
  "total_score": float,
  "total_score_pct": float,                 // 0..100
  "decision": "include" | "exclude" | "unsure"
}}
Rules:
- If evidence is insufficient, answer 'P' (if allowed) or 'N', and you may set decision='unsure'.
- Keep justifications SHORT (<= 20 words).
- Never output markdown or prose; JSON ONLY.
"""
    return rubric.strip()

# -----------------------------------------------------------------------------
# 5) Run assessment
# -----------------------------------------------------------------------------

if "quality_scored_rows" not in st.session_state:
    st.session_state["quality_scored_rows"] = []

def _score_papers(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    client = LLMClient(model=model_name)
    out: List[Dict[str, Any]] = []

    prog = st.progress(0.0, text="Starting quality assessment…")
    for idx, p in enumerate(papers, start=1):
        user = build_user_prompt_for_paper(p)
        try:
            resp = client.chat(system=SYSTEM, user=user, temperature=temp)
        except Exception as e:
            resp = ""
            st.error(f"LLM error on paper {idx}: {e}")

        parsed = _extract_json_block(resp) or {}
        answers = parsed.get("answers") or []
        justifs = parsed.get("justifications") or []
        per_q = parsed.get("score_per_question") or []

        # compute totals ourselves (trust, but verify)
        # Map answers -> base score, then multiply by weight
        def base_for(a: str) -> float:
            a = (a or "").strip().upper()
            if a == "Y": return float(y_val)
            if a == "P" and "P" in scheme: return float(p_val)
            return float(n_val)

        if not per_q or len(per_q) != len(questions):
            per_q = []
            for i in range(len(questions)):
                base = base_for(answers[i] if i < len(answers) else "N")
                per_q.append(base * weights[i])

        total = float(sum(per_q))
        pct = float(0.0 if max_possible <= 0 else (total / max_possible) * 100.0)

                # LLM's own decision (for info only)
        ai_decision_raw = (parsed.get("decision", "") or "").lower()

        # Authoritative decision: score vs cut-off
        decision = "include" if total >= float(cut_off) else "exclude"

        # attach QA + decisions to paper
        enriched = dict(p)
        enriched["qa"] = {
            "answers": answers[:len(questions)],
            "justifications": justifs[:len(questions)],
            "score_per_question": per_q[:len(questions)],
        }
        enriched["total_score"] = round(total, 4)
        enriched["total_score_pct"] = round(pct, 2)
        # score-based decision used for inclusion/exclusion
        enriched["decision"] = decision
        # keep the model's own decision separately
        enriched["ai_decision_raw"] = ai_decision_raw or "unsure"


        out.append(enriched)
        prog.progress(idx / max(1, len(papers)), text=f"Scored {idx}/{len(papers)}")

        # polite tiny delay
        time.sleep(0.05)

    return out

st.markdown("---")
if st.button("▶️ Run AI quality assessment on included set", use_container_width=True):
    with st.spinner("Scoring included studies against your checklist…"):
        scored = _score_papers(candidates)

    st.session_state["quality_scored_rows"] = scored

# -----------------------------------------------------------------------------
# 6) Results view + downloads
# -----------------------------------------------------------------------------

scored_rows: List[Dict[str, Any]] = st.session_state.get("quality_scored_rows", [])

if not scored_rows:
    st.info("No scores yet. Click **Run AI quality assessment** above.")
    st.stop()

# Derive buckets from current cut_off (re-derivable live)
incl, excl, unsure = [], [], []
for r in scored_rows:
    score = float(r.get("total_score", 0.0))
    ai_dec = (r.get("ai_decision_raw", "") or "").lower()

    if score >= float(cut_off):
        # score passes threshold → always included
        incl.append(r)
    elif ai_dec == "unsure":
        # below threshold, but model flagged as unsure → keep separate
        unsure.append(r)
    else:
        # below threshold and model basically negative → exclude
        excl.append(r)


st.success(f"AI include: **{len(incl)}**  |  AI exclude (low quality): **{len(excl)}**  |  AI unsure: **{len(unsure)}**")

# Save the final sets for downstream pages (Data Extraction)
st.session_state["quality_included"] = incl
st.session_state["quality_excluded"] = excl
st.session_state["quality_unsure"] = unsure

# Previews
def _preview_list(name: str, items: List[Dict[str, Any]]):
    with st.expander(f"Preview {name} ({len(items)})", expanded=False):
        for r in items[:200]:  # cap rendering
            score_dec = r.get("decision")
            ai_dec = r.get("ai_decision_raw", "")
            extra = f" • LLM decision: {ai_dec}" if ai_dec else ""
            st.caption(
                f"Score: {r.get('total_score')} / {max_possible:g} "
                f"({r.get('total_score_pct')}%)  • Score-based decision: {score_dec}{extra}"
            )

            if r.get("qa"):
                qa = r["qa"]
                for i, (ans, why) in enumerate(zip(qa.get("answers", []), qa.get("justifications", [])), start=1):
                    st.write(f"Q{i}: **{ans}** — {why}")
            st.markdown("---")

_preview_list("Included for data extraction", incl)
_preview_list("Excluded (below cut-off)", excl)
_preview_list("Unsure", unsure)

# Downloads
st.markdown("### Downloads")
qcount = len(questions)

csv_all = _rows_to_csv(scored_rows, qcount)
csv_incl = _rows_to_csv(incl, qcount)
csv_excl = _rows_to_csv(excl, qcount)

json_all = json.dumps(scored_rows, ensure_ascii=False, indent=2)
json_incl = json.dumps(incl, ensure_ascii=False, indent=2)
json_excl = json.dumps(excl, ensure_ascii=False, indent=2)

d1, d2 = st.columns(2)
with d1:
    st.download_button("⬇️ Download ALL scored (CSV)", data=csv_all, file_name="quality_scored_all.csv", mime="text/csv", use_container_width=True)
    st.download_button("⬇️ Download INCLUDED only (CSV)", data=csv_incl, file_name="quality_included.csv", mime="text/csv", use_container_width=True)
with d2:
    st.download_button("⬇️ Download EXCLUDED + reason (CSV)", data=csv_excl, file_name="quality_excluded.csv", mime="text/csv", use_container_width=True)

d3, d4 = st.columns(2)
with d3:
    st.download_button("⬇️ Download ALL scored (JSON)", data=json_all, file_name="quality_scored_all.json", mime="application/json", use_container_width=True)
with d4:
    st.download_button("⬇️ Download INCLUDED only (JSON)", data=json_incl, file_name="quality_included.json", mime="application/json", use_container_width=True)
st.download_button("⬇️ Download EXCLUDED + reason (JSON)", data=json_excl, file_name="quality_excluded.json", mime="application/json", use_container_width=True)

st.info("Proceed to **Data Extraction** using the `quality_included` set saved in session.")
