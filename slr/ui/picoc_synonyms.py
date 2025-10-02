# slr/ui/picoc_synonyms.py
import sys, os, json, hashlib
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from slr.agents.agent import run_define_picoc

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
    st.session_state["ai_syns"] = data.get("synonyms", {})
    st.session_state["selected_synonyms"] = {}   # reset selections for a fresh run

# ---------------- Show results if available ----------------
ai_picoc = st.session_state.get("ai_picoc")
ai_syns  = st.session_state.get("ai_syns")

if ai_picoc and ai_syns:
    # PICOC preview
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

    # Synonyms with checkboxes (curation)
    st.subheader("Facet-wise synonyms (select what to keep)")
    prev_sel = st.session_state.get("selected_synonyms", {})

    def checklist(facet: str, items: list[str]) -> list[str]:
        if not items:
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
        items = ai_syns.get(facet, [])
        with st.expander(f"{facet} ({len(items)} terms)", expanded=True):
            curated[facet] = checklist(facet, items)

    st.session_state["selected_synonyms"] = curated
    st.markdown("---")
    st.write("**Selected counts:**", {k: len(v) for k, v in curated.items()})

    # Export curated synonyms + PICOC (for later pages)
    payload = {
        "topic": st.session_state.get("topic", ""),
        "picoc": ai_picoc,
        "synonyms_all": ai_syns,
        "synonyms_selected": curated,
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
