# slr/query/builder.py
from __future__ import annotations
from typing import Dict, List, Tuple, Iterable
import re

FacetMap = Dict[str, List[str]]

_WHITESPACE = re.compile(r"\s+")

def _norm_term(t: str) -> str:
    """Normalize a term for comparison and quoting."""
    t = (t or "").strip()
    t = _WHITESPACE.sub(" ", t)
    # strip surrounding quotes if user-entered
    if len(t) >= 2 and t[0] == t[-1] == '"':
        t = t[1:-1]
    return t

def _quote_if_needed(t: str) -> str:
    """Quote multi-word terms; escape internal quotes."""
    t = t.replace('"', '\\"')
    return f'"{t}"' if " " in t or "-" in t else t

def _dedup_preserve_order(items: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for it in items:
        key = it.lower()
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out

def build_boolean_query(selected: FacetMap) -> Tuple[str, Dict[str, List[str]]]:
    """
    Build a generic Boolean string:
      (t1 OR t2) AND (t3 OR t4) ...
    Only non-empty facets are included.
    Returns (query_string, parts_by_facet)
    """
    parts_by_facet: Dict[str, List[str]] = {}
    facet_order = ["Population", "Intervention", "Comparison", "Outcome", "Context"]

    for facet in facet_order:
        terms = selected.get(facet, []) or []
        cleaned = [_norm_term(t) for t in terms if _norm_term(t)]
        cleaned = _dedup_preserve_order(cleaned)
        quoted = [_quote_if_needed(t) for t in cleaned]
        if quoted:
            # Keep for display and for downstream adapters
            parts_by_facet[facet] = quoted

    # Build the Boolean string
    groups = []
    for facet in facet_order:
        terms = parts_by_facet.get(facet)
        if not terms:
            continue
        group = " OR ".join(terms) if len(terms) == 1 else f'({" OR ".join(terms)})'
        groups.append(group)

    query = " AND ".join(groups) if groups else ""
    return query, parts_by_facet
