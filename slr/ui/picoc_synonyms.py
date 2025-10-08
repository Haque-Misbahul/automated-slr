# slr/ui/picoc_synonyms.py
import sys, os, json, hashlib, re
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from slr.agents.agent import run_define_picoc

# === SBERT (minimal; score-only control) ======================================
from typing import List, Sequence, Tuple, Optional
import torch
from sentence_transformers import SentenceTransformer, util

DEFAULT_SBERT_MODEL = os.getenv("SBERT_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

@st.cache_resource(show_spinner=False)
def _load_sbert(model_name: str = DEFAULT_SBERT_MODEL, device: Optional[str] = None) -> SentenceTransformer:
    dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
    return SentenceTransformer(model_name, device=dev)

def _norm(t: str) -> str:
    t = (t or "").strip()
    return re.sub(r"\s+", " ", t)

def _sbert_filter(
    base_term: str,
    candidates: Sequence[str],
    *,
    context: str = "",
    min_score: float = 0.70,
    alpha: float = 0.7,   # weight for base vs. context (kept fixed; only score is user-controlled)
) -> List[Tuple[str, float]]:
    """
    Returns [(candidate, score)] with score >= min_score, sorted desc.
    """
    base = _norm(base_term)
    cands = [c.strip() for c in candidates if isinstance(c, str) and c.strip()]
    if not base or not cands:
        return []

    model = _load_sbert()
    ref_texts = [base]
    ctx = _norm(context)
    if ctx:
        ref_texts.append(ctx)

    ref_embs = model.encode(ref_texts, convert_to_tensor=True, normalize_embeddings=True)
    cand_embs = model.encode(cands, convert_to_tensor=True, normalize_embeddings=True)

    if ref_embs.dim() == 1:
        ref_embs = ref_embs.unsqueeze(0)

    if len(ref_texts) == 1:
        ref_emb = ref_embs[0:1]
    else:
        base_emb = ref_embs[0]
        ctx_emb = ref_embs[1:].mean(dim=0)
        ref_emb = (alpha * base_emb + (1.0 - alpha) * ctx_emb).unsqueeze(0)

    sims = util.cos_sim(ref_emb, cand_embs).squeeze(0)  # [num_candidates]
    pairs = [(cands[i], float(sims[i])) for i in range(len(cands))]
    pairs.sort(key=lambda x: x[1], reverse=True)
    return [(t, s) for (t, s) in pairs if s >= float(min_score)]
# ==============================================================================


# ---------------- UI setup ----------------
st.set_page_config(page_title="Planning → Step 1: PICOC & Synonyms", layout="wide")

def inject_css():
    for css_name in ("styles.css", "style.css"):
        css_path = os.path.join(os.path.dirname(__file__), css_name)
        if os.path.exists(css_path):
            with open(css_path, "r", encoding="utf-8") as f:
                st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
            return
    st.markdown("""
    <style>
      .block-container {padding-top: 0.8rem; padding-bottom: 0.8rem;}
      section[data-testid="stSidebar"] {padding-top: .5rem;}
      div[data-testid="stVerticalBlock"] {gap: .4rem !important;}
      label[data-baseweb="checkbox"] {font-size: 0.92rem;}
      h1, h2, h3 {margin-bottom: .4rem;}
    </style>""", unsafe_allow_html=True)

inject_css()

st.markdown("<h2 style='margin-top:25px;'>🧩 Planning • Step 1: Define PICOC & Synonyms (AI)</h2>", unsafe_allow_html=True)

# --- SBERT score control (only new UI element; default 0.70) ---
sbert_min = st.slider("SBERT minimum similarity (cosine)", 0.40, 0.95, 0.70, 0.01,
                      help="Only synonyms with cosine similarity ≥ this value will be shown.")

# ---------------- Topic input ----------------
topic = st.text_input(
    "Topic / initial idea",
    value=st.session_state.get("topic", ""),
    placeholder="e.g., LLM-based code review automation in software engineering",
)

# ---------------- Generate PICOC + synonyms ----------------
if st.button("Generate PICOC & Synonyms (AI)", use_container_width=True):
    seed = topic.strip()
    if not seed:
        st.warning("Please enter a topic/keyword first.")
        st.stop()
    with st.spinner("Calling LLM (gpt-oss-120b) to define PICOC and facet synonyms..."):
        try:
            data = run_define_picoc(seed)  # returns {"picoc": {...}, "synonyms": {...}}
        except Exception as e:
            st.error(f"LLM call failed: {e}")
            st.stop()

    # persist for later steps/pages
    st.session_state["topic"] = seed
    st.session_state["ai_picoc"] = data.get("picoc", {})
    st.session_state["ai_syns_original"] = data.get("synonyms", {})  # keep original
    st.session_state["selected_synonyms"] = {}   # reset selections for a fresh run

# ---------------- Show results if available ----------------
ai_picoc = st.session_state.get("ai_picoc")
ai_syns_original = st.session_state.get("ai_syns_original")

def _picoc_context_str(picoc: dict, topic_text: str) -> str:
    # Rich context improves SBERT precision; keep deterministic order
    parts = [
        f"Topic: {topic_text or ''}",
        f"Population: {picoc.get('population','')}",
        f"Intervention: {picoc.get('intervention','')}",
        f"Comparison: {picoc.get('comparison','')}",
        f"Outcome: {picoc.get('outcome','')}",
        f"Context: {picoc.get('context','')}",
    ]
    return " | ".join([p for p in parts if p and not p.endswith(': ')])

if ai_picoc and ai_syns_original:
    # PICOC preview (unchanged)
    st.subheader("PICOC")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Population:** {ai_picoc.get('population','')}")
        st.write(f"**Intervention:** {ai_picoc.get('intervention','')}")
        st.write(f"**Comparison:** {ai_picoc.get('comparison','')}")
    with col2:
        st.write(f"**Outcome:** {ai_picoc.get('outcome','')}")
        st.write(f"**Context:** {ai_picoc.get('context','')}")

    # helper for stable widget keys per topic (prevents checkbox resets)
    def topic_key_suffix(txt: str) -> str:
        return hashlib.sha1(txt.encode("utf-8")).hexdigest()[:8]
    key_suffix = topic_key_suffix(st.session_state.get("topic", ""))

    # ---- SBERT-verified synonyms (only change) ----
    # We filter ai_syns_original facet-by-facet using SBERT against the facet's PICOC text,
    # with the full PICOC+topic as semantic context. Only terms with score >= sbert_min survive.
    context_text = _picoc_context_str(ai_picoc, st.session_state.get("topic", ""))

    def sbert_verify_facet(facet_name: str, base_text: str, items: list[str]) -> list[str]:
        if not items:
            return []
        scored = _sbert_filter(base_text, items, context=context_text, min_score=float(sbert_min))
        # keep only terms (we don't display scores in this UI)
        return [t for (t, _) in scored]

    # Build filtered dict (without mutating the original one in session)
    ai_syns_filtered = {
        "Population":   sbert_verify_facet("Population",   ai_picoc.get("population", ""),   ai_syns_original.get("Population", [])),
        "Intervention": sbert_verify_facet("Intervention", ai_picoc.get("intervention", ""), ai_syns_original.get("Intervention", [])),
        "Comparison":   sbert_verify_facet("Comparison",   ai_picoc.get("comparison", ""),   ai_syns_original.get("Comparison", [])),
        "Outcome":      sbert_verify_facet("Outcome",      ai_picoc.get("outcome", ""),      ai_syns_original.get("Outcome", [])),
        "Context":      sbert_verify_facet("Context",      ai_picoc.get("context", ""),      ai_syns_original.get("Context", [])),
    }

    # Synonyms with checkboxes (curation) — SAME UI as before, just using filtered terms
    st.subheader("Facet-wise synonyms (select what to keep)")
    prev_sel = st.session_state.get("selected_synonyms", {})

    def checklist(facet: str, items: list[str]) -> list[str]:
        if not items:
            st.info(f"No terms passed SBERT ≥ {sbert_min:.2f} for **{facet}**.")
            return []
        cols = st.columns(4)  # compact 4-up grid
        selected = []
        prev = set(prev_sel.get(facet, []))
        for i, term in enumerate(items):
            col = cols[i % 4]
            default_checked = True if not prev else (term in prev)
            key = f"chk_{facet}_{i}_{key_suffix}"
            with col:
                keep = st.checkbox(term, key=key, value=default_checked)
            if keep:
                selected.append(term)
        return selected

    curated = {}
    for facet in ("Population", "Intervention", "Comparison", "Outcome", "Context"):
        items = ai_syns_filtered.get(facet, [])
        with st.expander(f"{facet} ({len(items)} terms)", expanded=True):
            curated[facet] = checklist(facet, items)

    st.session_state["ai_syns"] = ai_syns_filtered            # filtered copy for downstream
    st.session_state["selected_synonyms"] = curated
    st.markdown("---")
    st.write("**Selected counts:**", {k: len(v) for k, v in curated.items()})

    # Export curated synonyms + PICOC (for later pages)
    payload = {
        "topic": st.session_state.get("topic", ""),
        "picoc": ai_picoc,
        "synonyms_all": ai_syns_original,      # original (unfiltered)
        "synonyms_sbert_filtered": ai_syns_filtered,  # filtered view
        "synonyms_selected": curated,
        "sbert_min": float(sbert_min),
        "sbert_model": DEFAULT_SBERT_MODEL,
    }
    st.download_button(
        "Download PICOC + curated synonyms (JSON)",
        data=json.dumps(payload, ensure_ascii=False, indent=2),
        file_name="picoc_synonyms_curated.json",
        mime="application/json",
        use_container_width=True,
    )
else:
    st.info("Enter a topic and click **Generate PICOC & Synonyms (AI)**.")
