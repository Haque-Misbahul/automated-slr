# slr/tools/synonyms_wordnet.py
from typing import List, Dict
import re
from nltk.corpus import wordnet as wn
from .retrieval_crossref import crossref_titles_abstracts
from .prf_synonyms import prf_phrases
from .sbert_filter import SBERTScorer

# -----------------------------
# WordNet helpers (lightweight)
# -----------------------------
def wordnet_synonyms(term: str) -> List[str]:
    """Return WordNet synonyms for the head word in `term` (deduped)."""
    head = term.split()[-1]
    syns: set[str] = set()
    for s in wn.synsets(head):
        for l in s.lemmas():
            w = l.name().replace("_", " ")
            if w.lower() != head.lower():
                syns.add(w)
    out, seen = [], set()
    for w in syns:
        wl = w.lower()
        if wl not in seen:
            seen.add(wl)
            out.append(w)
    return out

def expand_picoc_wordnet(picoc: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Baseline: keep originals + WordNet synonyms for each facet."""
    expanded: Dict[str, List[str]] = {}
    for facet, terms in picoc.items():
        facet_terms: List[str] = []
        seen = set()
        for t in terms:
            t = t.strip()
            if not t:
                continue
            if t.lower() not in seen:
                seen.add(t.lower())
                facet_terms.append(t)
            for s in wordnet_synonyms(t):
                sl = s.lower()
                if sl not in seen:
                    seen.add(sl)
                    facet_terms.append(s)
        expanded[facet] = facet_terms[:12]
    return expanded

# -----------------------------
# PRF + cleaning + SBERT filter
# -----------------------------
BAD_TOKENS = {"amp", "nbsp"}

def _clean_candidate(x: str) -> str:
    """Normalize & filter noisy candidates (digits, very short words, long phrases)."""
    x = re.sub(r"<[^>]+>", " ", x)                     # drop tags
    x = x.replace("–", "-").replace("—", "-")
    x = re.sub(r"[^a-zA-Z\s-]", " ", x)                # keep letters + hyphen
    x = re.sub(r"\s+", " ", x).strip().lower()
    if not x:
        return ""
    if any(t in x.split() for t in BAD_TOKENS):
        return ""
    words = x.split()
    if not (1 <= len(words) <= 4):                      # 1–4 tokens
        return ""
    if any(len(w) <= 2 for w in words):                 # drop 1–2 letter acronyms
        return ""
    return x

def _prefer_patterns(seed_head: str, phrase: str) -> bool:
    """
    Generic shape checks (work for any term):
    - contains the head word
    - '<modifier> head'  or 'head <modifier>'
    - hyphen compounds with the head
    """
    if seed_head not in phrase:
        return False
    words = phrase.split()
    if len(words) == 1:
        return words[0] == seed_head
    if words[-1] == seed_head:                           # greedy algorithm
        return True
    if words[0] == seed_head:                            # algorithm design
        return True
    if f"{seed_head}-" in phrase or f"-{seed_head}" in phrase:
        return True
    return False

def expand_intervention_wordnet_prf_sbert(
    seed: str, target_count: int = 10, threshold: float = 0.65
) -> List[str]:
    """
    Combine WordNet + PRF (Crossref) candidates and keep only SBERT-similar terms (>= threshold).
    Always include the seed on top. Returns up to `target_count` items.
    """
    seed_head = seed.split()[-1].lower()

    # 1) Collect candidates
    cands: List[str] = []
    seen: set[str] = set()

    def add(x: str):
        xl = _clean_candidate(x)
        if xl and xl not in seen and _prefer_patterns(seed_head, xl):
            seen.add(xl)
            cands.append(xl)

    add(seed)                                    # seed
    for s in wordnet_synonyms(seed):             # WordNet
        add(s)

    # PRF from Crossref (titles+abstracts) -> bigrams/trigrams
    docs = crossref_titles_abstracts(seed, rows=30)
    for p in prf_phrases(seed, docs, top_k=120):
        add(p)

    # 2) SBERT filter (semantic closeness to the seed)
    scorer = SBERTScorer()                       # all-MiniLM-L6-v2 by default
    pairs = scorer.filter(seed, cands, threshold=threshold)  # [(term, score)], high→low

    # 3) Final list: seed first + best-by-score (unique)
    out: List[str] = [seed.lower()]
    for term, _ in pairs:
        if term != seed.lower() and term not in out:
            out.append(term)
        if len(out) >= target_count:
            break

    # 4) Fallback padding if very strict filter
    if len(out) < min(5, target_count):
        for p in cands:
            if p not in out:
                out.append(p)
            if len(out) >= target_count:
                break

    return out[:target_count]
