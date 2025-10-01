# slr/query/arxiv_api.py
from __future__ import annotations
from typing import List, Dict
from urllib.request import urlopen
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

ARXIV_API = "http://export.arxiv.org/api/query"

def build_url(search_query: str, start: int = 0, max_results: int = 20, sort_by: str = "relevance") -> str:
    """Build API URL with basic params."""
    params = {
        "search_query": search_query,
        "start": start,
        "max_results": max_results,
        "sortBy": sort_by,       # relevance | lastUpdatedDate | submittedDate
    }
    return f"{ARXIV_API}?{urlencode(params)}"

def fetch(search_query: str, start: int = 0, max_results: int = 20) -> List[Dict]:
    """Fetch and parse arXiv Atom feed into a simple list of dicts."""
    url = build_url(search_query, start=start, max_results=max_results)
    with urlopen(url) as resp:
        data = resp.read()
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    root = ET.fromstring(data)
    out: List[Dict] = []
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=ns) or "")[:10]
        link = ""
        for l in entry.findall("atom:link", ns):
            if l.get("rel") == "alternate":
                link = l.get("href", "")
                break
        authors = [a.findtext("atom:name", default="", namespaces=ns) or "" for a in entry.findall("atom:author", ns)]
        primary_cat = ""
        cat_el = entry.find("arxiv:primary_category", ns)
        if cat_el is not None:
            primary_cat = cat_el.get("term", "")
        out.append({
            "title": title,
            "authors": authors,
            "published": published,
            "category": primary_cat,
            "link": link,
            "summary": summary,
        })
    return out
