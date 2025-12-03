# slr/agents/taxonomy.py
import json
from typing import List, Dict, Any, Optional
from slr.llm.client import LLMClient

SYSTEM_PROMPT = """You are an expert in systematic literature reviews and taxonomy design.
You will receive: (a) PICOC, (b) optional research questions, and (c) a list of paper titles
(with optional abstracts and snippets of full text).
Your job: propose a concise hierarchical taxonomy (2–3 levels) that organizes the topic clearly.
Then assign each paper to exactly one deepest leaf. Keep the taxonomy balanced and not too granular.
Return STRICT JSON that matches the required schema, with no extra text.
"""


def _format_user_prompt(
    titles: List[str],
    paper_ids: List[str],
    abstracts: Optional[List[str]] = None,
    full_texts: Optional[List[str]] = None,   # 👈 NEW
    picoc: Optional[Dict[str, str]] = None,
    rqs: Optional[List[str]] = None,
    depth: int = 2,
    max_children_per_node: int = 6,
    abs_snip_len: int = 220,
    full_snip_len: int = 800,                 # 👈 NEW
) -> str:

    """
    Build the user prompt for taxonomy generation.

    - titles / paper_ids: required
    - abstracts: optional short context per paper
    - full_texts: optional longer snippets (decoded from PDF)
    """
    lines: List[str] = []

    # PICOC context
    if picoc:
        lines.append("PICOC:")
        for k in ("population", "intervention", "comparison", "outcome", "context"):
            if k in picoc and picoc[k]:
                lines.append(f"- {k.capitalize()}: {picoc[k]}")
        lines.append("")

    # Research questions
    if rqs:
        lines.append("Research Questions:")
        for i, q in enumerate(rqs, 1):
            lines.append(f"- RQ{i}: {q}")
        lines.append("")

    # Design constraints
    lines.append(f"Depth requested: {depth}")
    lines.append(f"Max children per node: {max_children_per_node}")
    lines.append("")

    # Papers list
    lines.append("Papers:")
    for i, title in enumerate(titles):
        abs_snip = ""
        full_snip = ""

        # Abstract snippet
        if abstracts and i < len(abstracts) and abstracts[i]:
            sn = abstracts[i].strip()
            if abs_snip_len > 0:
                sn = sn[:abs_snip_len] + ("..." if len(sn) > abs_snip_len else "")
            else:
                sn = ""
            abs_snip = f" | abs: {sn}" if sn else ""

        # Full-text snippet from PDF
        if full_texts and i < len(full_texts) and full_texts[i]:
            ft = full_texts[i].strip()
            if full_snip_len > 0:
                ft = ft[:full_snip_len] + ("..." if len(ft) > full_snip_len else "")
            else:
                ft = ""
            full_snip = f" | full: {ft}" if ft else ""

        pid = paper_ids[i] if i < len(paper_ids) else f"paper_{i}"
        lines.append(f"- [{pid}] {title}{abs_snip}{full_snip}")


    lines.append("")
    lines.append("Return STRICT JSON with keys: taxonomy, mapping, notes.")
    lines.append(
        "Taxonomy must be a tree object of the form "
        '{"name": "root", "children": [ {...}, ... ]}. '
        "Each mapping item must include: paper_id, title, path (array of node names from root-child down to leaf)."
    )
    return "\n".join(lines)


def generate_taxonomy(
    titles: List[str],
    paper_ids: List[str],
    abstracts: Optional[List[str]] = None,
    full_texts: Optional[List[str]] = None,   # 👈 NEW
    picoc: Optional[Dict[str, str]] = None,
    rqs: Optional[List[str]] = None,
    depth: int = 2,
    max_children_per_node: int = 6,
    model: str = "gpt-oss-120b",
    max_papers: int = 60,
    abs_snip_len: int = 220,
    full_snip_len: int = 800,                 # 👈 NEW
) -> Dict[str, Any]:

    """
    Call the LLM to produce a taxonomy + paper mapping with a small, retryable payload.

    full_texts (optional): list of strings (same order as titles) – typically text
    extracted from PDFs. Only short snippets are included in the prompt to keep
    tokens reasonable.
    """
    # Trim payload (titles + ids + abstracts + full_texts) to reduce 502 risk
        # Trim payload to reduce 502 risk
    if max_papers and len(titles) > max_papers:
        titles = titles[:max_papers]
        paper_ids = paper_ids[:max_papers]
        abstracts = abstracts[:max_papers] if abstracts else None
        full_texts = full_texts[:max_papers] if full_texts else None


    client = LLMClient(model=model)
    user = _format_user_prompt(
        titles=titles,
        paper_ids=paper_ids,
        abstracts=abstracts,
        full_texts=full_texts,                    # 👈 NEW
        picoc=picoc,
        rqs=rqs,
        depth=int(depth),
        max_children_per_node=int(max_children_per_node),
        abs_snip_len=int(abs_snip_len),
        full_snip_len=int(full_snip_len),         # 👈 NEW
    )


    try:
        raw = client.chat(
            system=SYSTEM_PROMPT,
            user=user,
            max_retries=4,
            request_timeout=75.0,
        )
    except Exception as e:
        # Friendly fallback
        return {
            "taxonomy": {"name": "root", "children": []},
            "mapping": [],
            "notes": f"LLM call failed: {e}",
        }

    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]

    try:
        data = json.loads(text)
    except Exception:
        data = {
            "taxonomy": {"name": "root", "children": []},
            "mapping": [],
            "notes": "LLM parse failed",
        }

    if not isinstance(data, dict) or "taxonomy" not in data or "mapping" not in data:
        data = {
            "taxonomy": {"name": "root", "children": []},
            "mapping": [],
            "notes": "LLM returned incomplete JSON",
        }

    return data
