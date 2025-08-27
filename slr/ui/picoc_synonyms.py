import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
from slr.tools.synonyms_wordnet import expand_intervention_wordnet_prf_sbert

st.set_page_config(page_title="One-box → Synonyms (SBERT filtered)", layout="wide")
st.title("🧩 User Input → Synonyms (SBERT ≥ 0.65)")

topic = st.text_input("Topic / keyword", "", placeholder="e.g., algorithm, systematic literature review, graph search")

if st.button("Generate synonyms"):
    seed = topic.strip()
    if not seed:
        st.warning("Please enter a topic/keyword first.")
    else:
        with st.spinner("Expanding with WordNet + PRF + SBERT..."):
            # PICOC with intervention only
            picoc = {"population": [], "intervention": [seed], "comparison": [], "outcome": [], "context": []}
            synonyms = expand_intervention_wordnet_prf_sbert(seed, target_count=10, threshold=0.62)
            result = {"population": [], "intervention": synonyms, "comparison": [], "outcome": [], "context": []}

        st.subheader("PICOC used")
        #st.json(picoc)

        st.subheader("Synonyms (SBERT ≥ 0.65)")
        #st.json(result)
        st.json(synonyms)
