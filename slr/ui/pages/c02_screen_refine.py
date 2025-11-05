# slr/ui/pages/c02_screen_refine.py
import sys, os, io, csv, json, re
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# allow absolute imports from project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import streamlit as st
from slr.llm.client import LLMClient

st.set_page_config(page_title="Conducting → Step 3: Selection & Refinement", layout="wide")

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def normalize_title(t: str) -> str:
    if not t:
        return ""
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def parse_year(dt_str: str) -> Optional[int]:
    if not dt_str:
        return None
    m = re.match(r"(\d{4})", dt_str)
    return int(m.group(1)) if m else None

def load_rows_from_csv(file) -> List[Dict]:
    text = file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    rows: List[Dict] = []
    for r in reader:
        authors_str = r.get("authors", "") or ""
        authors = [a.strip() for a in authors_str.split(",") if a.strip()]
        rows.append({
            "id": r.get("id", ""),
            "title": r.get("title", ""),
            "summary": r.get("summary", ""),
            "published": r.get("published", ""),
            "updated": r.get("updated", ""),
            "authors": authors,
            "category": r.get("category", ""),
            "link": r.get("link", ""),
        })
    return rows

def rows_to_csv(rows: List[Dict], extra_cols: Optional[List[str]] = None) -> str:
    extra_cols = extra_cols or []
    cols = ["id", "title", "summary", "published", "updated", "authors", "category", "link"] + extra_cols
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(cols)
    for r in rows:
        authors = ", ".join(r.get("authors", [])) if isinstance(r.get("authors"), list) else (r.get("authors") or "")
        base = [
            r.get("id", ""),
            (r.get("title", "") or "").replace("\n", " ").strip(),
            (r.get("summary", "") or "").replace("\n", " ").strip(),
            r.get("published", ""),
            r.get("updated", ""),
            authors,
            r.get("category", ""),
            r.get("link", ""),
        ]
        for c in extra_cols:
            base.append(r.get(c, ""))
        w.writerow(base)
    return out.getvalue()

# -------- Accept BOTH naming styles from earlier steps --------
def normalize_criteria_keys(crit: Dict) -> Dict:
    """
    Accept both:
      - {"include","exclude","year_from","year_to"}
      - {"inclusion","exclusion","years":{"from","to"}}
    Return unified keys: {"inclusion":[], "exclusion":[], "years":{"from":..,"to":..}}
    """
    inclusion = crit.get("inclusion")
    exclusion = crit.get("exclusion")
    years     = crit.get("years")

    if inclusion is None and "include" in crit:
        inclusion = crit.get("include", [])
    if exclusion is None and "exclude" in crit:
        exclusion = crit.get("exclude", [])
    if years is None and ("year_from" in crit or "year_to" in crit):
        years = {"from": crit.get("year_from"), "to": crit.get("year_to")}

    return {
        "inclusion": inclusion or [],
        "exclusion": exclusion or [],
        "years": years or {},
    }

# ---------------- AI helper funcs ----------------
def safe_list(x):
    return x if isinstance(x, list) else []

def build_policy_text(crit_norm: Dict, research_questions: List[str]) -> str:
    inc = safe_list(crit_norm.get("inclusion", []))
    exc = safe_list(crit_norm.get("exclusion", []))
    rqs = safe_list(research_questions)

    lines = []
    if rqs:
        lines.append("RESEARCH QUESTIONS:")
        for i, rq in enumerate(rqs, 1):
            lines.append(f"- RQ{i}: {rq}")
        lines.append("")
    if inc:
        lines.append("INCLUSION CRITERIA:")
        for i, c in enumerate(inc, 1):
            lines.append(f"- I{i}: {c}")
        lines.append("")
    if exc:
        lines.append("EXCLUSION CRITERIA:")
        for i, c in enumerate(exc, 1):
            lines.append(f"- E{i}: {c}")
        lines.append("")
    return "\n".join(lines).strip()

def paper_to_text(r: Dict) -> str:
    authors = ", ".join(r.get("authors", [])) if isinstance(r.get("authors"), list) else (r.get("authors") or "")
    # If abstracts are huge and you hit token limits, you can trim here, e.g. summary[:2000]
    return (
        f"ID: {r.get('id','')}\n"
        f"Title: {r.get('title','').strip()}\n"
        f"Authors: {authors}\n"
        f"Year: {parse_year(r.get('published','')) or ''}\n"
        f"Category: {r.get('category','')}\n"
        f"Abstract: {r.get('summary','').strip()}\n"
        f"Link: {r.get('link','')}\n"
    ).strip()

def parse_ai_array(s: str) -> Optional[List[Dict]]:
    """
    Extract one top-level JSON object with key 'results' that contains a list.
    Be forgiving if the model wrapped it with prose.
    """
    # try direct parse
    try:
        obj = json.loads(s)
        if isinstance(obj, dict) and isinstance(obj.get("results"), list):
            return obj["results"]
    except Exception:
        pass

    # fallback: extract first {...}
    m = re.search(r'\{.*\}', s, flags=re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        if isinstance(obj, dict) and isinstance(obj.get("results"), list):
            return obj["results"]
    except Exception:
        return None
    return None

def batched(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def make_system_prompt() -> str:
    return (
        "You are assisting a systematic literature review. "
        "Decide if a candidate paper should be INCLUDED, EXCLUDED, or marked as UNSURE "
        "based strictly on the provided Research Questions and Inclusion/Exclusion criteria. "
        "Respond ONLY with compact JSON using this exact structure:\n"
        "{ \"results\": [\n"
        "  {\"decision\":\"include|exclude|unsure\",\"reason\":\"...\",\"matched_rules\":[\"...\"]},\n"
        "  ... one item per paper in the batch ...\n"
        "]}\n"
        "If information is insufficient or ambiguous, use 'unsure'. Be concise."
    )

def make_user_prompt(policy: str, papers: List[Dict]) -> str:
    """
    Ask the model to return EXACTLY one JSON object with an array named 'results'.
    The array length must equal the number of papers.
    """
    chunks = [f"POLICY\n{policy}\n\n"]
    for idx, r in enumerate(papers, 1):
        chunks.append(f"=== PAPER {idx} ===\n{paper_to_text(r)}")
    chunks.append(
        "\nINSTRUCTIONS\n"
        "Return EXACTLY ONE JSON object named 'results' with one object per paper, in order.\n"
        "Valid decisions: 'include' | 'exclude' | 'unsure'.\n"
        "Schema per item: {\"decision\":\"...\",\"reason\":\"...\",\"matched_rules\":[...]}\n"
        "Output format (and nothing else):\n"
        "{\"results\": [ {..paper1..}, {..paper2..}, ... ]}"
    )
    return "\n".join(chunks)

# -------------------------------------------------------------------
# Planning artifacts (from previous steps)
# -------------------------------------------------------------------
topic     = st.session_state.get("topic", "")
criteria  = st.session_state.get("criteria", {})           # Step 4 (varied schema)
sources   = st.session_state.get("sources", {})            # Step 3
qcheck    = st.session_state.get("quality_checklist", {})  # Step 5 (optional)

# Accept both "research_questions" and "rqs"
research_questions: List[str] = (
    st.session_state.get("research_questions")
    or st.session_state.get("rqs")
    or []
)

if topic:
    st.caption(f"Current topic: **{topic}**")

st.markdown("<h2 style='margin-top:20px;'>🧹 Conducting • Step 3: Study selection & refinement</h2>", unsafe_allow_html=True)
st.write(
    "This step de-duplicates and applies basic automatic filters based on your planning artifacts. "
    "Optionally, you can run **AI-assisted refinement** using your Research Questions and Inclusion/Exclusion criteria."
)

# -------------------------------------------------------------------
# Load raw studies (from session or upload)
# -------------------------------------------------------------------
rows: List[Dict] = st.session_state.get("gathered_rows", [])
st.markdown("### Load raw studies")
if rows:
    st.success(f"Loaded {len(rows)} studies from session (Step 2).")
else:
    up = st.file_uploader("Upload raw studies (CSV or JSON) exported from Step 2", type=["csv", "json"])
    if up:
        try:
            if (getattr(up, "type", "") or "").endswith("/json") or up.name.lower().endswith(".json"):
                rows = json.loads(up.read().decode("utf-8"))
            else:
                rows = load_rows_from_csv(up)
            st.success(f"Loaded {len(rows)} studies from upload.")
        except Exception as e:
            st.error(f"Failed to parse file: {e}")

if not rows:
    st.info("No raw studies found. Go to **Conducting → Build & Gather (arXiv)** and fetch studies first.")
    st.stop()

# -------------------------------------------------------------------
# Deduplication
# -------------------------------------------------------------------
st.markdown("### Deduplication")
dedup_key = st.selectbox("Choose deduplication key", ["normalized title", "id", "title + year"], index=0)
keep_rule = st.selectbox("When duplicates found, keep …", ["first occurrence", "latest by year"], index=0)

def perform_dedup(items: List[Dict]) -> Tuple[List[Dict], int]:
    seen: Dict[str, Dict] = {}
    drops = 0
    for r in items:
        if dedup_key == "id":
            k = (r.get("id", "") or "").strip().lower()
        elif dedup_key == "title + year":
            yr = parse_year(r.get("published", "")) or 0
            k = f"{normalize_title(r.get('title',''))}::{yr}"
        else:
            k = normalize_title(r.get("title", ""))

        if k not in seen:
            seen[k] = r
        else:
            if keep_rule == "latest by year":
                y_old = parse_year(seen[k].get("published", "")) or 0
                y_new = parse_year(r.get("published", "")) or 0
                if y_new > y_old:
                    seen[k] = r
            drops += 1
    return list(seen.values()), drops

deduped, dropped = perform_dedup(rows)
st.write(f"Deduped to **{len(deduped)}** (removed {dropped}).")

# -------------------------------------------------------------------
# Automatic filters (basic, reproducible)
# -------------------------------------------------------------------
st.markdown("### Automatic filters (from planning)")

crit_norm = normalize_criteria_keys(criteria or {})

# Years window (accept both schemas)
years = crit_norm.get("years") or {}
try:
    y_from_default = int(years.get("from", 1900)) if years.get("from") is not None else 1900
except Exception:
    y_from_default = 1900
try:
    y_to_default = int(years.get("to", datetime.now().year)) if years.get("to") is not None else datetime.now().year
except Exception:
    y_to_default = datetime.now().year

# arXiv CS categories (from Step 3)
sel_cats: List[str] = []
if isinstance(sources, dict):
    raw = sources.get("arxiv_categories") or sources.get("categories") or []
    if isinstance(raw, list):
        sel_cats = [str(c).strip() for c in raw if str(c).strip()]

colf1, colf2 = st.columns(2)
with colf1:
    y_from = st.number_input("From year", min_value=1900, max_value=2100, value=y_from_default, step=1)
with colf2:
    y_to   = st.number_input("To year", min_value=1900, max_value=2100, value=y_to_default, step=1)

cat_explain = ", ".join(sel_cats) if sel_cats else "any cs.*"
st.caption(f"Category filter: **{cat_explain}**")

def auto_screen(items: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    included: List[Dict] = []
    excluded: List[Dict] = []
    cat_allow: Optional[set] = set(sel_cats) if sel_cats else None

    for r in items:
        yr = parse_year(r.get("published", ""))
        cat = (r.get("category", "") or "").strip()

        # Year filter
        if yr is not None and (yr < int(y_from) or yr > int(y_to)):
            rr = dict(r)
            rr["reason"] = f"year {yr} outside [{y_from}-{y_to}]"
            excluded.append(rr)
            continue

        # Computer Science only
        if not cat.startswith("cs."):
            rr = dict(r)
            rr["reason"] = f"non-CS category: {cat or 'N/A'}"
            excluded.append(rr)
            continue

        # Enforce selected categories if provided
        if cat_allow and cat not in cat_allow:
            rr = dict(r)
            rr["reason"] = f"category not in selected sources: {cat}"
            excluded.append(rr)
            continue

        included.append(r)

    return included, excluded

inc, exc = auto_screen(deduped)
st.success(f"Auto-include: **{len(inc)}**  |  Auto-exclude: **{len(exc)}**")

# -------------------------------------------------------------------
# AI-assisted refinement (Research Questions + Inclusion/Exclusion)
# -------------------------------------------------------------------
st.markdown("### AI-assisted refinement (RQ + I/E criteria)")

policy_text = build_policy_text(crit_norm, research_questions)

with st.expander("Show applied RQs and criteria", expanded=False):
    st.code(policy_text or "No research questions/criteria found in session.", language="markdown")

col_ai1, col_ai2, col_ai3 = st.columns([1,1,1])
with col_ai1:
    use_ai = st.checkbox(
        "Use AI refinement on auto-included set",
        value=False,
        help="Runs an LLM check over the auto-included papers using your RQs and I/E criteria."
    )
with col_ai2:
    max_batch = st.number_input("Batch size", min_value=1, max_value=50, value=10, step=1,
                                help="Papers sent to the model per request.")
with col_ai3:
    temp = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.1,
                     help="Lower = more deterministic.")

ai_inc: List[Dict] = []
ai_exc: List[Dict] = []
ai_unsure: List[Dict] = []

def run_ai_refinement(papers: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    client = LLMClient()  # uses env + defaults from slr/llm/client.py
    inc_ai, exc_ai, unsure_ai = [], [], []

    if not policy_text:
        st.warning("No research questions or criteria found in session; AI refinement will default to 'unsure'.")
        return [], [], [dict(r, **{"ai_decision": "unsure", "ai_reason": "No RQs/criteria available"}) for r in papers]

    for batch in batched(papers, int(max_batch)):
        sys_prompt = make_system_prompt()
        usr_prompt = make_user_prompt(policy_text, batch)

        # allocate generous tokens: ~450 per paper, capped at 6000
        max_tok = min(6000, 450 * max(1, len(batch)))

        try:
            raw = client.chat(system=sys_prompt, user=usr_prompt, temperature=float(temp), max_tokens=max_tok)
        except Exception as e:
            st.error(f"LLM error: {e}")
            break

        items = parse_ai_array(raw or "") or []
        if len(items) != len(batch):
            st.warning(
                f"Model returned {len(items)} results for a batch of {len(batch)}; "
                "filling missing items as 'unsure'."
            )
            if len(items) < len(batch):
                items = items + [{} for _ in range(len(batch) - len(items))]
            else:
                items = items[:len(batch)]

        for r, parsed in zip(batch, items):
            parsed = parsed or {}
            decision = str(parsed.get("decision", "unsure")).lower().strip()
            reason = (parsed.get("reason") or "").strip()
            matched = parsed.get("matched_rules") or []
            rr = dict(r)
            rr["ai_decision"] = decision if decision in {"include","exclude","unsure"} else "unsure"
            rr["ai_reason"] = reason
            rr["ai_matched_rules"] = matched

            if rr["ai_decision"] == "include":
                inc_ai.append(rr)
            elif rr["ai_decision"] == "exclude":
                exc_ai.append(rr)
            else:
                unsure_ai.append(rr)

    return inc_ai, exc_ai, unsure_ai

if use_ai:
    st.info("Running AI refinement on the **auto-included** set...")
    ai_inc, ai_exc, ai_unsure = run_ai_refinement(inc)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.success(f"AI include: {len(ai_inc)}")
    with c2:
        st.error(f"AI exclude: {len(ai_exc)}")
    with c3:
        st.warning(f"AI unsure: {len(ai_unsure)}")

    choice = st.radio(
        "Which set should count as INCLUDED for downloads below?",
        options=[
            "Auto-included (no AI)",
            "AI-included (recommended)",
            "AI-included + Unsure (broad)"
        ],
        index=1,
        horizontal=False
    )

    if choice == "AI-included (recommended)":
        final_inc = ai_inc
        final_exc = ai_exc + ai_unsure
    elif choice == "AI-included + Unsure (broad)":
        final_inc = ai_inc + ai_unsure
        final_exc = ai_exc
    else:
        final_inc = inc
        final_exc = exc

    st.session_state["screened_rows"] = final_inc
    st.session_state["screened_excluded"] = final_exc

    with st.expander("Preview AI-included", expanded=False):
        st.dataframe([{k: v for k, v in r.items() if k in ("id","title","ai_reason","ai_matched_rules")} for r in ai_inc],
                     use_container_width=True)
    with st.expander("Preview AI-excluded", expanded=False):
        st.dataframe([{k: v for k, v in r.items() if k in ("id","title","ai_reason","ai_matched_rules")} for r in ai_exc],
                     use_container_width=True)
    with st.expander("Preview AI-unsure", expanded=False):
        st.dataframe([{k: v for k, v in r.items() if k in ("id","title","ai_reason","ai_matched_rules")} for r in ai_unsure],
                     use_container_width=True)
else:
    st.session_state["screened_rows"] = inc
    st.session_state["screened_excluded"] = exc

# -------------------------------------------------------------------
# Downloads
# -------------------------------------------------------------------
st.markdown("### Downloads")

if use_ai:
    csv_inc = rows_to_csv(st.session_state["screened_rows"], extra_cols=["ai_decision","ai_reason"])
    json_inc = json.dumps(st.session_state["screened_rows"], ensure_ascii=False, indent=2)
    csv_exc = rows_to_csv(st.session_state["screened_excluded"], extra_cols=["reason","ai_decision","ai_reason"])
    json_exc = json.dumps(st.session_state["screened_excluded"], ensure_ascii=False, indent=2)
else:
    csv_inc = rows_to_csv(st.session_state["screened_rows"])
    json_inc = json.dumps(st.session_state["screened_rows"], ensure_ascii=False, indent=2)
    csv_exc = rows_to_csv(st.session_state["screened_excluded"], extra_cols=["reason"])
    json_exc = json.dumps(st.session_state["screened_excluded"], ensure_ascii=False, indent=2)

c_d1, c_d2 = st.columns(2)
with c_d1:
    st.download_button("⬇️ Download INCLUDED (CSV)", data=csv_inc,
                       file_name="included_studies.csv", mime="text/csv", use_container_width=True)
    st.download_button("⬇️ Download INCLUDED (JSON)", data=json_inc,
                       file_name="included_studies.json", mime="application/json", use_container_width=True)
with c_d2:
    st.download_button("⬇️ Download EXCLUDED + reason (CSV)", data=csv_exc,
                       file_name="excluded_studies.csv", mime="text/csv", use_container_width=True)
    st.download_button("⬇️ Download EXCLUDED + reason (JSON)", data=json_exc,
                       file_name="excluded_studies.json", mime="application/json", use_container_width=True)

# -------------------------------------------------------------------
# Quality checklist template (optional)
# -------------------------------------------------------------------
st.markdown("---")
st.subheader("Quality scoring template (optional)")

if isinstance(qcheck, dict) and qcheck.get("questions"):
    qs = qcheck.get("questions", [])
    scheme = qcheck.get("scheme", "Y/N")  # "Y/N" or "Y/P/N"
    out = io.StringIO()
    w = csv.writer(out)
    hdr = ["id", "title"] + [f"Q{i+1}" for i in range(len(qs))] + ["total_score"]
    w.writerow(hdr)
    for r in st.session_state.get("screened_rows", []):
        w.writerow([r.get("id", ""), r.get("title", "")] + ["" for _ in qs] + [""])
    tmpl = out.getvalue()
    st.download_button(
        f"⬇️ Download Quality Checklist Template (scheme: {scheme})",
        data=tmpl,
        file_name="quality_scoring_template.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.caption("Fill the per-paper answers offline or in the next UI, then compute total_score. "
               "You can also integrate this with your Step-5 page.")
else:
    st.info("No quality checklist found from planning. You can still proceed, or go back to **Planning → Step 5** to define one.")
