# slr/ui/pages/d01_taxonomy.py
import sys, os, json, io, csv
from typing import List, Dict, Any, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
import streamlit as st
import requests

from slr.agents.taxonomy import generate_taxonomy

st.set_page_config(page_title="📚 Taxonomy generation (AI)", layout="wide")

# Optional PDF → text (for full-paper taxonomy)
try:
    from PyPDF2 import PdfReader  # type: ignore
except Exception:  # PyPDF2 not installed or import error
    PdfReader = None


def force_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


def _guess_pdf_url(paper: Dict[str, Any]) -> str:
    """
    Heuristic to guess a PDF URL for a paper.

    - Uses explicit `pdf_url` if present.
    - For arXiv links (abs), converts to pdf link.
    - Otherwise returns empty string.
    """
    # Explicit field from upstream pipeline
    pdf = str(paper.get("pdf_url") or "").strip()
    if pdf:
        return pdf

    # Look at URL / link / id / arxiv_id for arXiv patterns
    candidates = [
        paper.get("url"),
        paper.get("link"),
        paper.get("id"),
        paper.get("arxiv_id"),
    ]
    for val in candidates:
        s = str(val or "").strip()
        if not s:
            continue
        if "arxiv.org" in s:
            # normalize abs→pdf
            if "/abs/" in s:
                s = s.replace("/abs/", "/pdf/")
            if not s.endswith(".pdf"):
                s = s.rstrip("/") + ".pdf"
            return s

    return ""


def _pdf_bytes_to_text(data: bytes, max_pages: int = 10) -> str:
    """Best-effort: decode a PDF into plain text (first max_pages pages)."""
    if not PdfReader:
        # No dependency installed; caller can still rely on abstracts only.
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        texts: List[str] = []
        for i, page in enumerate(reader.pages[:max_pages]):
            t = page.extract_text() or ""
            texts.append(t)
        return "\n\n".join(texts).strip()
    except Exception:
        return ""


st.markdown("<h2>📚 Taxonomy generation (AI)</h2>", unsafe_allow_html=True)

# ------------------------------------------------------------------------
# Load input sets from previous steps
# ------------------------------------------------------------------------
included = None
source_name = None

# 1) Prefer the quality-assessed set (used by Data extraction)
if st.session_state.get("quality_included"):
    included = st.session_state["quality_included"]
    source_name = "quality_included (after quality assessment)"
# 2) Fall back to the screened set if quality step was skipped
elif st.session_state.get("screened_rows"):
    included = st.session_state["screened_rows"]
    source_name = "screened_rows (after screening)"

ai_picoc  = st.session_state.get("ai_picoc", {})
rq_list   = st.session_state.get("rq_list", [])
topic     = st.session_state.get("topic", "")

if topic:
    st.caption(f"Current topic: **{topic}**")

if not included:
    st.info(
        "No studies found for taxonomy. "
        "Please finish **Conducting → Screening** (and optionally **Quality assessment (AI)**) first."
    )
    st.stop()

st.success(f"{len(included)} papers available for taxonomy (source: **{source_name}**).")


titles: List[str] = [str(r.get("title", "")) for r in included]
paper_ids: List[str] = [str(r.get("id", "")) or f"paper_{i}" for i, r in enumerate(included)]
abstracts: List[str] = [str(r.get("summary", "")) for r in included]

with st.expander("Input snapshot", expanded=False):
    st.write(f"{len(titles)} papers available")
    st.json({"sample_title": titles[:3], "PICOC": ai_picoc, "RQs": rq_list})

# ------------------------------------------------------------------------
# PDF fetch for taxonomy (new)
# ------------------------------------------------------------------------
st.markdown("### PDFs for taxonomy (optional)")

# Where we store PDFs for taxonomy purposes
pdf_store: Dict[str, Dict[str, Any]] = st.session_state.get("taxonomy_pdfs", {})
if not isinstance(pdf_store, dict):
    pdf_store = {}
    st.session_state["taxonomy_pdfs"] = pdf_store

# Pre-compute candidate URLs
pdf_candidates: Dict[str, str] = {}
for pid, paper in zip(paper_ids, included):
    pdf_candidates[pid] = _guess_pdf_url(paper)

num_candidates = sum(1 for u in pdf_candidates.values() if u)
num_already = sum(1 for pid in paper_ids if pid in pdf_store)

st.caption(
    f"PDF candidates found for **{num_candidates} / {len(included)}** papers. "
    f"Already fetched: **{num_already}**."
)

if st.button("📥 Fetch PDFs for all candidate papers", use_container_width=True):
    fetched = 0
    skipped = 0
    failures: List[str] = []

    for pid, paper in zip(paper_ids, included):
        pdf_url = pdf_candidates.get(pid) or ""
        if not pdf_url:
            continue
        if pid in pdf_store:
            skipped += 1
            continue
        try:
            resp = requests.get(pdf_url, timeout=30)
            resp.raise_for_status()
            pdf_bytes = resp.content
            pdf_store[pid] = {
                "url": pdf_url,
                "bytes": pdf_bytes,
            }
            fetched += 1
        except Exception as e:
            failures.append(f"{pid}: {e}")

    st.session_state["taxonomy_pdfs"] = pdf_store

    msg = f"Fetched **{fetched}** PDFs"
    if skipped:
        msg += f"; skipped **{skipped}** already-fetched."
    st.success(msg)
    if failures:
        st.warning(
            "Some PDFs could not be fetched (showing up to 5):\n\n"
            + "\n".join(f"- {f}" for f in failures[:5])
        )
    force_rerun()

if not PdfReader:
    st.info(
        "PyPDF2 is not installed, so taxonomy will still rely mainly on titles & abstracts. "
        "Install `PyPDF2` if you want full-text snippets from PDFs."
    )

# ------------------------------------------------------------------------
# Taxonomy generation controls
# ------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns([1, 1, 1, 1.3])
with c1:
    depth = st.selectbox("Depth", [2, 3], index=0)
with c2:
    max_children = st.slider("Max children/node", min_value=3, max_value=10, value=6)
with c3:
    max_papers = st.number_input(
        "Max papers to send",
        min_value=20,
        max_value=120,
        value=60,
        step=10,
        help="Trim to avoid 502s. You can re-run with a higher number if stable.",
    )
with c4:
    abs_len = st.slider(
        "Abstract snippet length",
        min_value=0,
        max_value=400,
        value=220,
        step=20,
        help="Shorter → smaller payload. 0 disables abstracts.",
    )

# ------------------------------------------------------------------------
# Generate taxonomy
# ------------------------------------------------------------------------
if st.button("🚀 Generate taxonomy (AI)", use_container_width=True):
    # Build full-text list from any fetched PDFs (same order as titles/paper_ids)
    full_texts: Optional[List[str]] = None
    if pdf_store and PdfReader:
        full_texts = []
        for pid in paper_ids:
            entry = pdf_store.get(pid)
            if entry and entry.get("bytes"):
                txt = _pdf_bytes_to_text(entry["bytes"])
            else:
                txt = ""
            full_texts.append(txt)

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
            full_texts=full_texts,
            full_snip_len=1500,  # keep snippets shorter than full papers
        )

    st.session_state["taxonomy_ai"] = data
    if isinstance(data, dict) and data.get("taxonomy", {}).get("children"):
        st.success("Draft taxonomy generated.")
    else:
        st.warning(f"LLM returned empty taxonomy. Notes: {data.get('notes')}")

    force_rerun()

# ------------------------------------------------------------------------
# Preview + downloads
# ------------------------------------------------------------------------
data = st.session_state.get("taxonomy_ai")

def _render_tree(node: Dict[str, Any], level: int = 0):
    name = node.get("name", "")
    children = node.get("children", [])
    pad = " " * level
    st.write(f"{pad}• **{name}**")
    for ch in children:
        _render_tree(ch, level + 1)

if isinstance(data, dict):
    st.markdown("### Preview taxonomy")
    colL, colR = st.columns([1, 1])
    with colL:
        _render_tree(data.get("taxonomy", {"name": "root", "children": []}))
    with colR:
        st.json(data.get("taxonomy", {}), expanded=False)

    st.markdown("### Paper → leaf mapping")
    mapping: List[Dict[str, Any]] = data.get("mapping", [])
    st.write(f"{len(mapping)} assignments")
    st.dataframe(mapping, use_container_width=True, height=360)

    st.markdown("---")
    tax_json = json.dumps(data, ensure_ascii=False, indent=2)
    st.download_button(
        "⬇️ Download taxonomy JSON",
        data=tax_json,
        file_name="taxonomy_ai.json",
        mime="application/json",
        use_container_width=True,
    )

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["paper_id", "title", "path"])
    for m in mapping:
        w.writerow([m.get("paper_id", ""), m.get("title", ""), " / ".join(m.get("path", []))])
    st.download_button(
        "⬇️ Download mapping CSV",
        data=out.getvalue(),
        file_name="taxonomy_mapping.csv",
        mime="text/csv",
        use_container_width=True,
    )
else:
    st.info("Configure options and click **Generate taxonomy (AI)**.")
