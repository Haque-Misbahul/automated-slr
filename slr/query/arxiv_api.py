# slr/query/arxiv_api.py
"""
arXiv API helper.

Public functions:
- build_url(search_query, start=0, max_results=50, sort_by=None) -> str
- fetch_page(search_query, start=0, max_results=50, sort_by=None) -> (rows, total_results)
- fetch(search_query, start=0, max_results=50, sort_by=None) -> rows   (compat wrapper)

Features:
- Uses HTTPS and follows redirects (fixes 301 errors).
- Always respects `max_results` (no hidden clamps).
- Returns feed's opensearch:totalResults for stable pagination.
- Stable optional `sort_by`: 'relevance' | 'lastUpdatedDate' | 'submittedDate'.
- If `feedparser` is unavailable, uses a stdlib XML fallback.
"""

from typing import List, Dict, Optional, Tuple
import urllib.parse
import httpx

# Optional dependency: feedparser
try:
    import feedparser  # type: ignore
    HAVE_FEEDPARSER = True
except Exception:
    HAVE_FEEDPARSER = False

# Stdlib XML fallback
import xml.etree.ElementTree as ET

ARXIV_API = "https://export.arxiv.org/api/query"  # << HTTPS
USER_AGENT = "automated-slr (github.com/Haque-Misbahul/automated-slr)"

# XML namespaces used by arXiv Atom feeds
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def build_url(
    search_query: str,
    start: int = 0,
    max_results: int = 50,
    sort_by: Optional[str] = None,
) -> str:
    """Build an arXiv API URL."""
    params = {
        "search_query": search_query or "",
        "start": str(int(start)),
        "max_results": str(int(max_results)),
    }
    if sort_by:
        # 'relevance' | 'lastUpdatedDate' | 'submittedDate'
        params["sortBy"] = sort_by
    return ARXIV_API + "?" + urllib.parse.urlencode(params)


def _entry_to_row_dict(e: Dict) -> Dict:
    """Convert a feedparser entry to our row format (fast path)."""
    authors = [a.get("name", "") for a in (e.get("authors") or []) if a.get("name")]
    link = ""
    for l in e.get("links", []) or []:
        if l.get("rel") == "alternate":
            link = l.get("href", "") or ""
            break
    cat = e.get("arxiv_primary_category") or {}
    primary_cat = cat.get("term", "") if isinstance(cat, dict) else ""
    return {
        "id": e.get("id", "") or "",
        "title": (e.get("title", "") or "").strip(),
        "summary": (e.get("summary", "") or "").strip(),
        "published": e.get("published", "") or "",
        "updated": e.get("updated", "") or "",
        "authors": authors,
        "category": primary_cat,
        "link": link,
    }


def _parse_with_feedparser(xml_text: str) -> Tuple[List[Dict], int]:
    fp = feedparser.parse(xml_text)
    entries = fp.entries or []
    rows = [_entry_to_row_dict(e) for e in entries]
    # opensearch:totalResults (string usually)
    total_results = 0
    try:
        total_results = int(
            getattr(fp.feed, "opensearch_totalresults", 0)
            or fp.feed.get("opensearch_totalresults", 0)  # type: ignore[attr-defined]
        )
    except Exception:
        total_results = 0
    if not total_results:
        total_results = len(rows)
    return rows, total_results


def _text(el: Optional[ET.Element]) -> str:
    return (el.text or "").strip() if el is not None else ""


def _parse_with_stdlib(xml_text: str) -> Tuple[List[Dict], int]:
    """
    Minimal Atom parser using ElementTree (fallback when feedparser isn't installed).
    Extracts the fields we use downstream.
    """
    root = ET.fromstring(xml_text)

    # totalResults
    total_results = 0
    tr = root.find("opensearch:totalResults", NS)
    if tr is not None:
        try:
            total_results = int(_text(tr) or "0")
        except Exception:
            total_results = 0

    rows: List[Dict] = []
    for entry in root.findall("atom:entry", NS):
        entry_id = _text(entry.find("atom:id", NS))
        title = _text(entry.find("atom:title", NS))
        summary = _text(entry.find("atom:summary", NS))
        published = _text(entry.find("atom:published", NS))
        updated = _text(entry.find("atom:updated", NS))

        # authors
        authors: List[str] = []
        for a in entry.findall("atom:author", NS):
            nm = _text(a.find("atom:name", NS))
            if nm:
                authors.append(nm)

        # primary link (rel="alternate")
        link = ""
        for l in entry.findall("atom:link", NS):
            if l.get("rel") == "alternate" and l.get("href"):
                link = l.get("href") or ""
                break

        # primary category term
        primary_cat = ""
        pc = entry.find("arxiv:primary_category", NS)
        if pc is not None:
            primary_cat = pc.get("term", "") or ""

        rows.append(
            {
                "id": entry_id,
                "title": title,
                "summary": summary,
                "published": published,
                "updated": updated,
                "authors": authors,
                "category": primary_cat,
                "link": link,
            }
        )

    if not total_results:
        total_results = len(rows)
    return rows, total_results


def fetch_page(
    search_query: str,
    start: int = 0,
    max_results: int = 50,
    sort_by: Optional[str] = None,
) -> Tuple[List[Dict], int]:
    """
    Fetch a single page and also return the feed's totalResults for robust pagination.
    This function never clamps `max_results` internally.
    """
    url = build_url(search_query, start=start, max_results=max_results, sort_by=sort_by)
    headers = {"User-Agent": USER_AGENT}
    # follow_redirects=True fixes 301
    resp = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    xml_text = resp.text

    if HAVE_FEEDPARSER:
        return _parse_with_feedparser(xml_text)
    else:
        return _parse_with_stdlib(xml_text)


def fetch(
    search_query: str,
    start: int = 0,
    max_results: int = 50,
    sort_by: Optional[str] = None,
) -> List[Dict]:
    """Backward-compatible wrapper returning only rows."""
    rows, _ = fetch_page(search_query, start=start, max_results=max_results, sort_by=sort_by)
    return rows
