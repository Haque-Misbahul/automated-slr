import re
from collections import Counter
from typing import List

# Small stopword list to avoid extra installs
STOP = set("""
a an and are as at be but by for from has have in into is it its of on or that the their to was were with without within over under about between during across against after before
we you they he she this those these there here which who whom whose been being doing done such not no yes can could may might should would will
""".split())

def normalize(text: str) -> List[str]:
    # Lowercase, remove XML-like tags, keep letters/numbers, collapse spaces
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^a-z0-9\s\-]", " ", text.lower())
    text = re.sub(r"\s+", " ", text).strip()
    return text.split()

def ngrams(tokens: List[str], n: int) -> List[str]:
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]

def prf_phrases(seed: str, docs: List[str], top_k: int = 15) -> List[str]:
    """
    Extract frequent bigrams/trigrams from docs, preferring phrases
    that contain the seed head word or 'algorithm'/'method' family terms.
    """
    seed_head = seed.split()[-1].lower()
    counts = Counter()
    for d in docs:
        toks = [t for t in normalize(d) if t not in STOP]
        for n in (2, 3):
            for g in ngrams(toks, n):
                if (seed_head in g) or ("algorithm" in g) or ("method" in g):
                    counts[g] += 1
    # rank by count then by length (prefer more specific)
    ranked = [p for p, _ in counts.most_common(200)]
    # quick cleanups: remove leading/trailing generic words
    cleaned = []
    for p in ranked:
        words = [w for w in p.split() if w not in STOP]
        if len(words) >= 2:
            cleaned.append(" ".join(words))
    # de-dup while preserving order
    seen = set(); out = []
    for p in cleaned:
        if p not in seen:
            seen.add(p); out.append(p)
    return out[:top_k]
