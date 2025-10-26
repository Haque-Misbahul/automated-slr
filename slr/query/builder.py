# slr/query/builder.py
from __future__ import annotations
from typing import Dict, List, Tuple, Iterable, Optional
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
    return f'"{t}"' if (" " in t or "-" in t) else t


def _dedup_preserve_order(items: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for it in items:
        key = it.lower()
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def _clean_terms(terms: Iterable[str]) -> List[str]:
    """
    normalize, drop empties, dedup, then quote multi-word strings.
    returns a list of terms like ["array", "\"numeric dataset\""]
    """
    cleaned = [_norm_term(t) for t in terms if _norm_term(t)]
    cleaned = _dedup_preserve_order(cleaned)
    quoted = [_quote_if_needed(t) for t in cleaned]
    return quoted


def _group_to_boolean(terms: List[str]) -> str:
    """
    Turn a list of already-quoted terms into:
       term1 OR term2 OR ...
    wrapped in (...) if there is more than 1.
    """
    if not terms:
        return ""
    if len(terms) == 1:
        return terms[0]
    return "(" + " OR ".join(terms) + ")"


def build_boolean_query(
    selected: FacetMap,
    topic: Optional[str] = None,
) -> Tuple[str, Dict[str, List[str]]]:
    """
    Build a generic Boolean string:
        (<topic terms>) AND (<Population terms>) AND (<Intervention terms>) ...

    We add:
    - topic terms: from the user topic string (e.g. "sorting algorithm") to broaden recall
      This becomes its own OR-group, like ("sorting algorithm" OR "sorting algorithms")
      (for now we just include the raw topic; if user typed multiple words, it's quoted)

    Only non-empty groups are included in the final AND chain.

    Returns:
        query_string: full Boolean string
        parts_by_facet: dict of facet -> cleaned term list (quoted)
                        also includes a special key "_topic" if topic was present
    """
    parts_by_facet: Dict[str, List[str]] = {}

    # 1. topic block
    # we treat the "topic" as its own pseudo-facet so we can AND it with others
    # this makes sure arXiv sees that direct phrase too
    topic_terms: List[str] = []
    if topic:
        # we can include singular & plural variant if it's trivial "sorting algorithm"
        # to keep it simple and safe we only include the raw topic user typed
        topic_terms = _clean_terms([topic])
        if topic_terms:
            parts_by_facet["_topic"] = topic_terms

    # 2. normal PICOC facet order
    facet_order = ["Population", "Intervention", "Comparison", "Outcome", "Context"]
    for facet in facet_order:
        raw_terms = selected.get(facet, []) or []
        quoted = _clean_terms(raw_terms)
        if quoted:
            parts_by_facet[facet] = quoted

    # 3. Build final Boolean
    # order: topic first (broad anchor), then rest
    groups: List[str] = []
    if "_topic" in parts_by_facet:
        groups.append(_group_to_boolean(parts_by_facet["_topic"]))

    for facet in facet_order:
        if facet in parts_by_facet:
            groups.append(_group_to_boolean(parts_by_facet[facet]))

    query = " AND ".join([g for g in groups if g]) if groups else ""

    return query, parts_by_facet
