import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import json
import streamlit as st
# ❌ OLD: from slr.tools.synonyms_wordnet import expand_intervention_wordnet_prf_sbert
# ✅ NEW:
from slr.agents.agent import run_define_picoc

st.set_page_config(page_title="Planning → PICOC & Synonyms (AI)", layout="wide")
st.title("🧩 Planning • Step 1: Define PICOC & Synonyms (AI)")

topic = st.text_input(
    "Topic / initial idea",
    "",
    placeholder="e.g., LLM-based code review automation in software engineering"
)

if st.button("Generate PICOC & Synonyms (AI)", use_container_width=True):
    seed = topic.strip()
    if not seed:
        st.warning("Please enter a topic/keyword first.")
    else:
        with st.spinner("Calling LLM (gpt-oss-120b) to define PICOC and facet synonyms..."):
            try:
                data = run_define_picoc(seed)  # returns {"picoc": {...}, "synonyms": {...}}
            except Exception as e:
                st.error(f"LLM call failed: {e}")
                st.stop()

        # --- PICOC ---
        st.subheader("PICOC")
        picoc = data.get("picoc", {})
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Population:** {picoc.get('population','')}")
            st.write(f"**Intervention:** {picoc.get('intervention','')}")
            st.write(f"**Comparison:** {picoc.get('comparison','')}")
        with col2:
            st.write(f"**Outcome:** {picoc.get('outcome','')}")
            st.write(f"**Context:** {picoc.get('context','')}")

        # --- Synonyms per facet ---
        st.subheader("Facet-wise synonyms (AI-proposed)")
        syns = data.get("synonyms", {})
        for facet in ("Population", "Intervention", "Comparison", "Outcome", "Context"):
            items = syns.get(facet, [])
            if items:
                st.markdown(f"**{facet}**")
                st.write(", ".join(items))

        # Optional: JSON download
        st.download_button(
            label="Download PICOC + Synonyms (JSON)",
            data=json.dumps(data, ensure_ascii=False, indent=2),
            file_name="picoc_synonyms_ai.json",
            mime="application/json",
            use_container_width=True
        )
