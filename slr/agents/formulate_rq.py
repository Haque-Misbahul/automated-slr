# slr/agents/formulate_rq.py
from __future__ import annotations
import json, re
from typing import Dict, Any, List
from slr.llm.client import LLMClient

SYSTEM = (
    "You assist with the PLANNING phase of a Systematic Literature Review (SLR). "
    "Given a PICOC description, propose concise, researchable Research Questions (RQs). "
    "Favor clarity and operationalizable wording suitable for academic SLR protocols."
)

USER_TMPL = """PICOC:
- Population: {population}
- Intervention: {intervention}
- Comparison: {comparison}
- Outcome: {outcome}
- Context: {context}

Requirements:
- Propose 5–7 RQs tailored to this PICOC.
- Mix types: effectiveness/impact, comparison, context-specific, measurement/metrics, challenges/trade-offs.
- Keep each RQ < 25 words, precise and answerable.
- If some PICOC facets are empty, omit them naturally.
- Return STRICT JSON only:

{{
  "rqs": [
    "RQ1 text ...",
    "RQ2 text ...",
    "RQ3 text ...",
    "RQ4 text ...",
    "RQ5 text ...",
    "RQ6 text ...",
    "RQ7 text ..."
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

def formulate_rqs_from_picoc(picoc: Dict[str, str], max_rqs: int = 7) -> Dict[str, Any]:
    """Return dict: {"rqs": [...], "notes": "..."} (aim for 5–7 RQs)."""
    llm = LLMClient(model="gpt-oss-120b")
    u = USER_TMPL.format(
        population=picoc.get("population",""),
        intervention=picoc.get("intervention",""),
        comparison=picoc.get("comparison",""),
        outcome=picoc.get("outcome",""),
        context=picoc.get("context",""),
    )
    raw = llm.chat(system=SYSTEM, user=u)
    data = _extract_json(raw)
    rqs: List[str] = [s.strip() for s in data.get("rqs", []) if isinstance(s, str) and s.strip()]
    # normalize length / count to max 7
    rqs = rqs[:max_rqs]
    return {"rqs": rqs, "notes": (data.get("notes", "") or "").strip()}
