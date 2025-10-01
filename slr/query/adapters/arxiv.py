# slr/query/adapters/arxiv.py
from __future__ import annotations
from typing import Dict, List, Iterable
from urllib.parse import quote_plus
import re

# parts_by_facet comes from builder.build_boolean_query(...)
#   e.g., {"Intervention": ['"quick sort"','"merge sort"'], ...}

Fields = Iterable[str]

def _strip_quotes(s: str) -> str:
    s = (s or "").strip()
    if len(s) >= 2 and s[0] == s[-1] == '"':
        return s[1:-1]
    return s

def _per_term_field_group(term: str, fields: Fields) -> str:
    """
    For one term, build (ti:"term" OR abs:"term" ...)
    """
    t = _strip_quotes(term).replace('"', '\\"')
    pieces = [f'{f}:"{t}"' for f in fields]
    return "(" + " OR ".join(pieces) + ")"

def build_arxiv_query(
    parts_by_facet: Dict[str, List[str]],
    fields: Fields = ("ti", "abs")
) -> str:
    """
    Build an arXiv search_query string from facet parts.
    Within a facet -> OR across terms (each term expanded to selected fields).
    Across facets -> AND.
    """
    facet_order = ["Population", "Intervention", "Comparison", "Outcome", "Context"]
    groups: List[str] = []

    for facet in facet_order:
        terms = parts_by_facet.get(facet, [])
        if not terms:
            continue
        per_term = [_per_term_field_group(t, fields) for t in terms]
        group = "(" + " OR ".join(per_term) + ")" if len(per_term) > 1 else per_term[0]
        groups.append(group)

    return " AND ".join(groups) if groups else ""

def arxiv_api_url(search_query: str, start: int = 0, max_results: int = 50) -> str:
    """
    Build a copy-pasteable arXiv API URL.
    Docs: http://export.arxiv.org/api_help/docs/user-manual.html
    """
    sq = quote_plus(search_query)
    return f"http://export.arxiv.org/api/query?search_query={sq}&start={start}&max_results={max_results}"

_HYPHENS = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2212]")  # various unicode dashes
_WS = re.compile(r"\s+")

def _sanitize(s: str) -> str:
    # normalize unicode dashes to ASCII, collapse whitespace, strip
    s = _HYPHENS.sub("-", s or "")
    s = _WS.sub(" ", s).strip()
    return s

def _strip_quotes(s: str) -> str:
    s = (s or "").strip()
    if len(s) >= 2 and s[0] == s[-1] == '"':
        return s[1:-1]
    return s

def _per_term_field_group(term: str, fields: Iterable[str]) -> str:
    """
    For one term, build (ti:"term" OR abs:"term" ...)
    """
    t = _sanitize(_strip_quotes(term)).replace('"', '\\"')
    pieces = [f'{f}:"{t}"' for f in fields]
    return "(" + " OR ".join(pieces) + ")"
