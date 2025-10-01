# slr/agents/define_picoc.py
from __future__ import annotations
import json
import re
from typing import Dict, Any
from slr.llm.client import LLMClient

SYSTEM_PROMPT = (
    "You are an assistant that prepares the PLANNING phase for a Systematic Literature Review (SLR) "
    "in computer science. Follow Kitchenham & Charters and Carrera-Rivera et al. "
    "First, define PICOC (Population, Intervention, Comparison, Outcome, Context). "
    "Then propose concise, domain-appropriate SYNONYMS (aka alike terms) for each PICOC facet. "
    "Output STRICT JSON ONLY. No prose, no markdown."
)

USER_PROMPT_TEMPLATE = """Topic: {topic}

Requirements:
- Give PICOC fields as short, human-readable strings (empty string if N/A).
- For each facet, give 5–12 synonyms/near-equivalents (strings), specific to computer science.
- Avoid generic words like "system", "method", "approach", "framework", "based", "model".
- Do NOT include explanations or citations.

Return JSON with this exact schema and keys:
{{
  "picoc": {{
    "population": "<string or empty>",
    "intervention": "<string or empty>",
    "comparison": "<string or empty>",
    "outcome": "<string or empty>",
    "context": "<string or empty>"
  }},
  "synonyms": {{
    "Population": ["..."],
    "Intervention": ["..."],
    "Comparison": ["..."],
    "Outcome": ["..."],
    "Context": ["..."]
  }}
}}
"""

JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

def _extract_json(text: str) -> Dict[str, Any]:
    """Best-effort: grab the first JSON object from the text and load it."""
    m = JSON_OBJECT_RE.search(text.strip())
    if not m:
        raise ValueError("Model did not return JSON.")
    return json.loads(m.group(0))

def define_picoc(topic: str) -> Dict[str, Any]:
    """
    Calls the LLM (gpt-oss-120b) to generate PICOC and facet-wise synonyms.
    Returns a dict with keys 'picoc' and 'synonyms'.
    """
    # IMPORTANT: professor asked to use gpt-oss-120b for the agent
    llm = LLMClient(model="gpt-oss-120b")
    user = USER_PROMPT_TEMPLATE.format(topic=topic)
    raw = llm.chat(system=SYSTEM_PROMPT, user=user)
    data = _extract_json(raw)

    # light validation & normalization
    data.setdefault("picoc", {})
    data.setdefault("synonyms", {})
    for k in ("population", "intervention", "comparison", "outcome", "context"):
        data["picoc"].setdefault(k, "")

    for facet in ("Population", "Intervention", "Comparison", "Outcome", "Context"):
        arr = data["synonyms"].get(facet, [])
        # dedupe & strip empties
        cleaned = []
        seen = set()
        for t in arr:
            if not isinstance(t, str):
                continue
            s = t.strip()
            if not s:
                continue
            if s.lower() in seen:
                continue
            seen.add(s.lower())
            cleaned.append(s)
        data["synonyms"][facet] = cleaned[:12]  # keep it tight for UI
    return data
