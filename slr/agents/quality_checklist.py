# slr/agents/quality_checklist.py
from __future__ import annotations
import json, re
from typing import Dict, Any, List, Optional
from slr.llm.client import LLMClient

SYSTEM = (
    "You assist with the PLANNING phase of a Systematic Literature Review (SLR). "
    "Your job is to propose a concise quality assessment checklist for candidate studies. "
    "The checklist is answered with Yes / Partial / No responses and used for study selection."
)

USER_TMPL = """You are helping define a **quality assessment checklist** for an SLR.

Topic:
- {topic}

PICOC (if available):
- Population: {population}
- Intervention: {intervention}
- Comparison: {comparison}
- Outcome: {outcome}
- Context: {context}

Existing screening criteria (if any):
- Inclusion rules: {include_rules}
- Exclusion rules: {exclude_rules}

User search keywords / query:
- {search_keywords}

Task:
1. Propose a SHORT quality assessment checklist for evaluating candidate studies.
2. Each item must be answerable with **Yes / Partial / No**.
3. For each item, assign a weight in {{1.0, 0.5, 0.0}} where:
   - 1.0 = essential for study quality.
   - 0.5 = important but not strictly essential.
   - 0.0 = optional / nice-to-have.
4. Focus on: clarity of research goals, soundness of methodology, dataset/experiment details,
   validity of analysis, reporting of results, discussion of limitations, and replicability.

STYLE RULES (IMPORTANT):
- Each checklist question MUST be short (max ~12 words).
- No examples, no parentheses, no 'e.g.', no enumeration inside the question.
- Use clear, direct language such as:
  - "States clear research objectives."
  - "Describes dataset or experimental setup."
  - "Discusses threats to validity."
- Do NOT repeat the same idea in different wording.

OUTPUT FORMAT:
Return STRICT JSON only, with no commentary:

{{
  "questions": [
    {{
      "question": "Short Yes/Partial/No question 1",
      "weight": 1.0
    }},
    {{
      "question": "Short Yes/Partial/No question 2",
      "weight": 0.5
    }}
  ]
}}

Number of items: target between {min_q} and {max_q} questions.
"""

JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> Dict[str, Any]:
    m = JSON_RE.search(text.strip())
    if not m:
        raise ValueError("Model did not return JSON.")
    return json.loads(m.group(0))


def _shorten_question(text: str) -> str:
    """
    Make a question concise and strip junk:
    - remove anything after ';'
    - drop parentheticals (...)
    - drop 'e.g.' and following details
    - collapse spaces
    - strip trailing '.'
    """
    if not text:
        return ""

    import re as _re
    t = text.strip()

    # drop everything after ';'
    t = t.split(";")[0]

    # remove (...) explanatory asides
    t = _re.sub(r"\([^)]*\)", "", t)

    # remove 'e.g.' / 'for example' / 'such as' and following
    t = _re.sub(r"\b(e\.g\.|for example|such as)\b.*", "", t, flags=_re.IGNORECASE)

    # collapse whitespace
    t = _re.sub(r"\s+", " ", t).strip()

    if t.endswith("."):
        t = t[:-1].strip()

    return t


def _fmt_rules_for_context(rules: Optional[List[str]]) -> str:
    if not rules:
        return "[]"
    cleaned = []
    seen = set()
    for r in rules:
        if isinstance(r, str):
            s = _shorten_question(r)
            if s and s.lower() not in seen:
                seen.add(s.lower())
                cleaned.append(s)
    return ", ".join(cleaned) if cleaned else "[]"


def _fmt_str(s: Optional[str]) -> str:
    return s.strip() if isinstance(s, str) else ""


def generate_quality_checklist(
    topic: str,
    picoc: Dict[str, str],
    criteria: Dict[str, Any],
    search_keywords: str,
    min_questions: int = 5,
    max_questions: int = 10,
    model_name: str = "gpt-oss-120b",
) -> List[Dict[str, Any]]:
    """
    Returns a list of items:
      [
        {"question": str, "weight": float},
        ...
      ]
    Questions are short and intended for Yes/Partial/No scoring.
    """
    llm = LLMClient(model=model_name)

    include_rules = criteria.get("include", []) if isinstance(criteria, dict) else []
    exclude_rules = criteria.get("exclude", []) if isinstance(criteria, dict) else []

    u = USER_TMPL.format(
        topic=_fmt_str(topic),
        population=_fmt_str(picoc.get("population", "")),
        intervention=_fmt_str(picoc.get("intervention", "")),
        comparison=_fmt_str(picoc.get("comparison", "")),
        outcome=_fmt_str(picoc.get("outcome", "")),
        context=_fmt_str(picoc.get("context", "")),
        include_rules=_fmt_rules_for_context(include_rules),
        exclude_rules=_fmt_rules_for_context(exclude_rules),
        search_keywords=_fmt_str(search_keywords),
        min_q=min_questions,
        max_q=max_questions,
    )

    raw = llm.chat(system=SYSTEM, user=u)
    data = _extract_json(raw)

    q_items = data.get("questions", [])
    results: List[Dict[str, Any]] = []

    for item in q_items:
        if not isinstance(item, dict):
            continue

        q_text = _shorten_question(str(item.get("question", "")).strip())
        if not q_text:
            continue

        # parse & clamp weight to {1.0, 0.5, 0.0}
        w_raw = item.get("weight", 1.0)
        try:
            w = float(w_raw)
        except (TypeError, ValueError):
            w = 1.0

        if w >= 0.75:
            w = 1.0
        elif w >= 0.25:
            w = 0.5
        else:
            w = 0.0

        results.append({"question": q_text, "weight": w})

    # enforce minimum number of questions, if needed
    fallback_sentence = "Reports sufficient methodological detail for appraisal"
    while len(results) < min_questions:
        results.append({"question": fallback_sentence, "weight": 1.0})

    # trim if too many
    if len(results) > max_questions:
        results = results[:max_questions]

    return results
