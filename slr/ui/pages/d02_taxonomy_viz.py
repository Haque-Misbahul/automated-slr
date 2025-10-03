# slr/ui/pages/d02_taxonomy_viz.py
import sys, os, json, io, csv
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import streamlit as st
import pandas as pd
import plotly.express as px
import graphviz
from typing import Optional, List, Dict

st.set_page_config(page_title="Taxonomy Visualization", layout="wide")

# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def count_leaves(node: dict) -> int:
    """Count all leaf nodes in a taxonomy dict."""
    ch = node.get("children") or []
    if not ch:
        return 1
    return sum(count_leaves(c) for c in ch)


def build_graphviz(
    dot: graphviz.Digraph,
    node: dict,
    parent_id: Optional[str] = None,
    idx: Optional[List[int]] = None,
):
    idx = idx or []
    node_id = "n_" + "_".join(map(str, idx)) if idx else "root"
    label = node.get("name", "Unnamed")
    leaves = count_leaves(node)
    dot.node(
        node_id,
        f"{label}\n({leaves} leaf{'s' if leaves == 1 else 's'})",
        shape="box",
        style="rounded,filled",
        fillcolor="#F2F7FF"
    )
    if parent_id is not None:
        dot.edge(parent_id, node_id)
    for i, ch in enumerate(node.get("children") or []):
        build_graphviz(dot, ch, node_id, idx + [i])


def taxonomy_to_rows(node: dict, path: Optional[List[str]] = None) -> List[Dict]:
    path = path or []
    name = node.get("name", "Unnamed")
    ch = node.get("children") or []
    if not ch:
        return [{"path": path + [name], "size": 1}]
    rows: List[Dict] = []
    for c in ch:
        rows += taxonomy_to_rows(c, path + [name])
    return rows


def df_from_assignments(assignments: list[dict]) -> pd.DataFrame:
    """Expect each assignment: {'paper_id': 'paper_0', 'title': '...', 'path': 'X / Y / Z'}"""
    return pd.DataFrame(assignments)

# --------------------------------------------------------------------------------------
# Load taxonomy from session or upload
# --------------------------------------------------------------------------------------
st.markdown("## 📚 Taxonomy Visualization")

tree = st.session_state.get("taxonomy_tree")  # set by d01_taxonomy.py
assignments = st.session_state.get("taxonomy_assignments", [])

with st.expander("Load taxonomy from file (optional)", expanded=False):
    up = st.file_uploader("Upload taxonomy.json", type=["json"])
    if up is not None:
        try:
            data = json.load(up)
            if isinstance(data, dict):
                tree = data
                st.success("Loaded taxonomy from upload.")
            else:
                st.error("taxonomy.json must be a JSON object (root node).")
        except Exception as e:
            st.error(f"Failed to parse JSON: {e}")

if not tree:
    st.warning("No taxonomy in memory. Generate it first on the 'taxonomy' page or upload a taxonomy.json above.")
    st.stop()

# --------------------------------------------------------------------------------------
# Graphviz Tree
# --------------------------------------------------------------------------------------
st.markdown("### 🌳 Taxonomy (Tree)")
col_gv, col_info = st.columns([2, 1])
with col_gv:
    try:
        dot = graphviz.Digraph("taxonomy", graph_attr={"rankdir": "TB"}, node_attr={"fontname": "Inter"})
        build_graphviz(dot, tree)
        st.graphviz_chart(dot, use_container_width=True)
    except Exception as e:
        st.error(f"Graphviz rendering failed. Ensure system Graphviz is installed. Error: {e}")

with col_info:
    st.markdown("**Root name:**")
    st.code(tree.get("name", "root"))
    st.markdown("**Leaves:**")
    st.code(count_leaves(tree))
    st.markdown("**JSON preview:**")
    st.json(tree)

# --------------------------------------------------------------------------------------
# Treemap & Sunburst
# --------------------------------------------------------------------------------------
rows = taxonomy_to_rows(tree)
df = pd.DataFrame(rows)
max_depth = max(len(p) for p in df["path"]) if not df.empty else 1
for i in range(max_depth):
    df[f"lvl{i}"] = df["path"].apply(lambda p: p[i] if i < len(p) else "")

st.markdown("### 🧩 Treemap (leaf counts)")
fig_tm = px.treemap(
    df,
    path=[f"lvl{i}" for i in range(max_depth)],
    values="size",
    color_discrete_sequence=px.colors.qualitative.Pastel,
)
fig_tm.update_layout(margin=dict(l=0, r=0, t=30, b=0))
st.plotly_chart(fig_tm, use_container_width=True)

st.markdown("### ☀️ Sunburst (radial taxonomy)")
fig_sb = px.sunburst(
    df,
    path=[f"lvl{i}" for i in range(max_depth)],
    values="size",
    color_discrete_sequence=px.colors.qualitative.Pastel,
)
fig_sb.update_layout(margin=dict(l=0, r=0, t=30, b=0))
st.plotly_chart(fig_sb, use_container_width=True)

# --------------------------------------------------------------------------------------
# Downloads
# --------------------------------------------------------------------------------------
st.markdown("### ⬇️ Downloads")
c1, c2, c3, c4 = st.columns(4)

# 1) taxonomy.json
with c1:
    st.download_button(
        "Download taxonomy.json",
        data=json.dumps(tree, ensure_ascii=False, indent=2),
        file_name="taxonomy.json",
        mime="application/json",
        use_container_width=True,
    )

# 2) assignments.csv (if present)
if assignments:
    with c2:
        df_assign = df_from_assignments(assignments)
        csv_buf = io.StringIO()
        df_assign.to_csv(csv_buf, index=False)
        st.download_button(
            "Download paper_to_leaf.csv",
            data=csv_buf.getvalue(),
            file_name="paper_to_leaf.csv",
            mime="text/csv",
            use_container_width=True,
        )

# 3) Treemap PNG (needs kaleido)
with c3:
    try:
        png = fig_tm.to_image(format="png", scale=2)
        st.download_button(
            "Download treemap (PNG)",
            data=png,
            file_name="taxonomy_treemap.png",
            mime="image/png",
            use_container_width=True,
        )
    except Exception:
        st.caption("Install `kaleido` for PNG export.")

# 4) Sunburst PNG (needs kaleido)
with c4:
    try:
        png2 = fig_sb.to_image(format="png", scale=2)
        st.download_button(
            "Download sunburst (PNG)",
            data=png2,
            file_name="taxonomy_sunburst.png",
            mime="image/png",
            use_container_width=True,
        )
    except Exception:
        st.caption("Install `kaleido` for PNG export.")
