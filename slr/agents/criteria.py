# slr/agents/criteria.py
from __future__ import annotations
import json, re
from typing import Dict, Any, List, Optional
from slr.llm.client import LLMClient

SYSTEM = (
    "You assist with the PLANNING phase of a Systematic Literature Review (SLR). "
    "Your job is to draft brief inclusion and exclusion criteria for study screening. "
    "You must adapt them to the provided PICOC scope and approved terminology/synonyms."
)

USER_TMPL = """You are helping define screening criteria for an SLR.

PICOC:
- Population: {population}
- Intervention: {intervention}
- Comparison: {comparison}
- Outcome: {outcome}
- Context: {context}

Approved terminology that the reviewers will screen for:
- Population terms: {pop_terms}
- Intervention terms: {int_terms}
- Comparison terms: {cmp_terms}
- Outcome terms: {out_terms}
- Context terms: {ctx_terms}

Task:
1. Create EXACTLY 5 Inclusion criteria: short, decisive rules describing when to KEEP a study.
2. Create EXACTLY 5 Exclusion criteria: short, decisive rules describing when to DISCARD a study.
3. Suggest a reasonable publication year range if the topic clearly relates to recent technologies 
   (e.g., deep learning, LLMs, cloud-native systems). Otherwise, set both years to null.


STYLE RULES (IMPORTANT):
- Each criterion MUST be a single short sentence or phrase (max ~15 words).
- No examples, no 'e.g.', no parentheses, no semicolons, no lists, no long clarifications.
- Use direct screening language. For example:
  - "Study evaluates one of the approved algorithms."
  - "Paper reports runtime or memory performance."
  - "Work is in computer science."
  - "Not English" (for exclusion).
- Tailor them to the PICOC. Mention algorithms / performance / comparison / context if relevant.
- Avoid filler like "the study" unless needed.
- At least some criteria MUST capture topical relevance based on the PICOC elements and terminology.


OUTPUT FORMAT:
Return STRICT JSON only with EXACTLY 5 items in each list:

{{
  "include": [
    "Inclusion rule 1",
    "Inclusion rule 2",
    "Inclusion rule 3",
    "Inclusion rule 4",
    "Inclusion rule 5"
  ],
  "exclude": [
    "Exclusion rule 1",
    "Exclusion rule 2",
    "Exclusion rule 3",
    "Exclusion rule 4",
    "Exclusion rule 5"
  ],
  "years": {{
    "from": null,
    "to": null
  }}
}}



If you cannot infer sensible years, set both 'from' and 'to' to null.
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
    uniq = []
    seen = set()
    for s in lst:
        if isinstance(s, str):
            s2 = s.strip()
            if s2 and s2.lower() not in seen:
                seen.add(s2.lower())
                uniq.append(s2)
    # join inline (just for LLM hinting context)
    return ", ".join(uniq)

def generate_criteria_from_picoc(
    picoc: Dict[str, str],
    synonyms: Dict[str, List[str]],
    model_name: str = "gpt-oss-120b",
) -> Dict[str, Any]:
    """
    Returns:
    {
      "include": [...],
      "exclude": [...],
      "years": { "from": int|None, "to": int|None }
    }
    """
    llm = LLMClient(model=model_name)

    u = USER_TMPL.format(
        population = picoc.get("population", ""),
        intervention = picoc.get("intervention", ""),
        comparison = picoc.get("comparison", ""),
        outcome = picoc.get("outcome", ""),
        context = picoc.get("context", ""),
        pop_terms = _fmt_list(synonyms.get("Population", [])),
        int_terms = _fmt_list(synonyms.get("Intervention", [])),
        cmp_terms = _fmt_list(synonyms.get("Comparison", [])),
        out_terms = _fmt_list(synonyms.get("Outcome", [])),
        ctx_terms = _fmt_list(synonyms.get("Context", [])),
    )

    raw = llm.chat(system=SYSTEM, user=u)
    data = _extract_json(raw)

    include_rules = [
        r.strip()
        for r in data.get("include", [])
        if isinstance(r, str) and r.strip()
    ]
    exclude_rules = [
        r.strip()
        for r in data.get("exclude", [])
        if isinstance(r, str) and r.strip()
    ]

    yrs = data.get("years", {}) or {}
    yr_from = yrs.get("from", None)
    yr_to   = yrs.get("to", None)

    # fallback: guarantee at least 5 each
    while len(include_rules) < 5:
        include_rules.append("Relevant to the defined technical scope")
    while len(exclude_rules) < 5:
        exclude_rules.append("Outside the defined technical scope")

    return {
        "include": include_rules,
        "exclude": exclude_rules,
        "years": {
            "from": yr_from if isinstance(yr_from, int) else None,
            "to":   yr_to   if isinstance(yr_to, int)   else None,
        },
    }
