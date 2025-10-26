# slr/agents/formulate_rq.py
from __future__ import annotations
import json, re
from typing import Dict, Any, List, Optional
from slr.llm.client import LLMClient

SYSTEM = (
    "You assist with the PLANNING phase of a Systematic Literature Review (SLR). "
    "Your job is to draft high-quality, academically appropriate Research Questions (RQs). "
    "You MUST follow the user's PICOC, and you SHOULD reuse the important terminology "
    "and synonyms they provide so the questions align with how the search will actually be performed. "
    "Write questions that are realistic to answer in an SLR."
)

# We'll embed both PICOC and synonyms in the user prompt.
USER_TMPL = """PICOC:
- Population: {population}
- Intervention: {intervention}
- Comparison: {comparison}
- Outcome: {outcome}
- Context: {context}

Approved terminology and synonyms (use these words when relevant):
- Population terms: {pop_terms}
- Intervention terms: {int_terms}
- Comparison terms: {cmp_terms}
- Outcome terms: {out_terms}
- Context terms: {ctx_terms}

Requirements:
- Propose 3–5 RQs tailored to this PICOC and approved terms.
- Mix types: effectiveness/impact, comparison, context-specific, measurement/metrics, and challenges/trade-offs.
- Each RQ must be < 25 words, precise, and answerable via evidence from literature.
- If some PICOC facets or synonym lists are empty, just skip them naturally.
- Avoid vague phrases like 'in general' or 'various fields' unless the Context is actually general.
- Return STRICT JSON only:

{{
  "rqs": [
    "RQ1 text ...",
    "RQ2 text ...",
    "RQ3 text ...",
    "RQ4 text ...",
    "RQ5 text ..."
  ],
  "notes": "1–2 sentences on scope/assumptions (optional)"
}}
"""

JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

def _extract_json(text: str) -> Dict[str, Any]:
    m = JSON_RE.search(text.strip())
    if not m:
        raise ValueError("Model did not return JSON.")
    return json.loads(m.group(0))

def _fmt_list(lst: Optional[List[str]]) -> str:
    if not lst:
        return "[]"
    # join as comma-separated string for readability in prompt
    return ", ".join(sorted(set([s for s in lst if isinstance(s, str) and s.strip()])))

def formulate_rqs_from_picoc(
    picoc: Dict[str, str],
    max_rqs: int = 5,
    synonyms: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    """
    Generate research questions from PICOC (+ optional synonyms).

    Args:
        picoc: {
            "population": "...",
            "intervention": "...",
            "comparison": "...",
            "outcome": "...",
            "context": "..."
        }

        max_rqs: maximum number of questions to keep (default 5).

        synonyms: {
            "Population":   [...],
            "Intervention": [...],
            "Comparison":   [...],
            "Outcome":      [...],
            "Context":      [...]
        }
        This should be the curated synonym lists selected by the user in Step 1.
        It's optional so old code won't break.
    """

    syn = synonyms or {}
    pop_terms = _fmt_list(syn.get("Population"))
    int_terms = _fmt_list(syn.get("Intervention"))
    cmp_terms = _fmt_list(syn.get("Comparison"))
    out_terms = _fmt_list(syn.get("Outcome"))
    ctx_terms = _fmt_list(syn.get("Context"))

    user_prompt = USER_TMPL.format(
        population=picoc.get("population", ""),
        intervention=picoc.get("intervention", ""),
        comparison=picoc.get("comparison", ""),
        outcome=picoc.get("outcome", ""),
        context=picoc.get("context", ""),
        pop_terms=pop_terms,
        int_terms=int_terms,
        cmp_terms=cmp_terms,
        out_terms=out_terms,
        ctx_terms=ctx_terms,
    )

    llm = LLMClient(model="gpt-oss-120b")
    raw = llm.chat(system=SYSTEM, user=user_prompt)
    data = _extract_json(raw)

    # normalize + trim
    rqs: List[str] = [
        s.strip()
        for s in data.get("rqs", [])
        if isinstance(s, str) and s.strip()
    ]
    rqs = rqs[:max_rqs]

    notes = (data.get("notes", "") or "").strip()

    return {
        "rqs": rqs,
        "notes": notes,
    }
