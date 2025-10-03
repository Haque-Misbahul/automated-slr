# slr/ui/pages/d01_taxonomy.py
import sys, os, json, io, csv
from typing import List, Dict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
import streamlit as st

from slr.agents.taxonomy import generate_taxonomy

st.set_page_config(page_title="📚 Taxonomy generation (AI)", layout="wide")

def force_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

st.markdown("<h2>📚 Taxonomy generation (AI)</h2>", unsafe_allow_html=True)

included = st.session_state.get("screened_rows", [])
ai_picoc  = st.session_state.get("ai_picoc", {})
rq_list   = st.session_state.get("rq_list", [])
topic     = st.session_state.get("topic", "")

if topic:
    st.caption(f"Current topic: **{topic}**")

if not included:
    st.info("No included studies found. Finish Conducting • Step 3 first.")
    st.stop()

titles: List[str]     = [str(r.get("title","")) for r in included]
paper_ids: List[str]  = [str(r.get("id","")) or f"paper_{i}" for i,r in enumerate(included)]
abstracts: List[str]  = [str(r.get("summary","")) for r in included]

with st.expander("Input snapshot", expanded=False):
    st.write(f"{len(titles)} papers available")
    st.json({"sample_title": titles[:3], "PICOC": ai_picoc, "RQs": rq_list})

c1, c2, c3, c4 = st.columns([1,1,1,1.3])
with c1:
    depth = st.selectbox("Depth", [2,3], index=0)
with c2:
    max_children = st.slider("Max children/node", min_value=3, max_value=10, value=6)
with c3:
    max_papers = st.number_input("Max papers to send", min_value=20, max_value=120, value=60, step=10,
                                 help="Trim to avoid 502s. You can re-run with a higher number if stable.")
with c4:
    abs_len = st.slider("Abstract snippet length", min_value=0, max_value=400, value=220, step=20,
                        help="Shorter → smaller payload. 0 disables abstracts.")

if st.button("🚀 Generate taxonomy (AI)", use_container_width=True):
    with st.spinner("Calling LLM to draft taxonomy..."):
        data = generate_taxonomy(
            titles=titles,
            paper_ids=paper_ids,
            abstracts=abstracts if abs_len > 0 else None,
            picoc=ai_picoc,
            rqs=rq_list,
            depth=int(depth),
            max_children_per_node=int(max_children),
            max_papers=int(max_papers),
            abs_snip_len=int(abs_len),
        )
    st.session_state["taxonomy_ai"] = data
    if data.get("taxonomy", {}).get("children"):
        st.success("Draft taxonomy generated.")
    else:
        st.warning(f"LLM returned empty taxonomy. Notes: {data.get('notes')}")
    force_rerun()

data = st.session_state.get("taxonomy_ai")

def _render_tree(node: Dict, level=0):
    name = node.get("name","")
    children = node.get("children",[])
    pad = " " * level
    st.write(f"{pad}• **{name}**")
    for ch in children:
        _render_tree(ch, level+1)

if data:
    st.markdown("### Preview taxonomy")
    colL, colR = st.columns([1,1])
    with colL:
        _render_tree(data.get("taxonomy", {"name":"root","children":[]}))
    with colR:
        st.json(data.get("taxonomy", {}), expanded=False)

    st.markdown("### Paper → leaf mapping")
    mapping: List[Dict] = data.get("mapping", [])
    st.write(f"{len(mapping)} assignments")
    st.dataframe(mapping, use_container_width=True, height=360)

    st.markdown("---")
    tax_json = json.dumps(data, ensure_ascii=False, indent=2)
    st.download_button("⬇️ Download taxonomy JSON", data=tax_json,
                       file_name="taxonomy_ai.json", mime="application/json", use_container_width=True)

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["paper_id","title","path"])
    for m in mapping:
        w.writerow([m.get("paper_id",""), m.get("title",""), " / ".join(m.get("path",[]))])
    st.download_button("⬇️ Download mapping CSV", data=out.getvalue(),
                       file_name="taxonomy_mapping.csv", mime="text/csv", use_container_width=True)
else:
    st.info("Configure options and click **Generate taxonomy (AI)**.")
