import requests

def crossref_titles_abstracts(query: str, rows: int = 20) -> list[str]:
    """
    Return a list of strings (titles + abstracts) for a quick PRF pass.
    Uses only requests. No heavy deps.
    """
    url = "https://api.crossref.org/works"
    params = {
        "query": query,
        "rows": rows,
        "select": "title,abstract"
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    items = r.json().get("message", {}).get("items", [])
    docs = []
    for it in items:
        title = (it.get("title") or [""])[0]
        abstract = it.get("abstract") or ""
        docs.append(f"{title}. {abstract}")
    return docs
