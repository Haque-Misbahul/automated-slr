from typing import List, Tuple
from sentence_transformers import SentenceTransformer, util

class SBERTScorer:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def score(self, seed: str, candidates: List[str]) -> List[Tuple[str, float]]:
        """Return [(candidate, cosine_similarity)], high-to-low."""
        if not candidates:
            return []
        seed_desc = f"{seed}: a step-by-step computational term related to the research topic"
        seed_emb = self.model.encode([seed_desc], normalize_embeddings=True)
        cand_emb = self.model.encode(candidates, normalize_embeddings=True)
        sims = util.cos_sim(seed_emb, cand_emb).squeeze().tolist()
        pairs = list(zip(candidates, sims))
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs

    def filter(self, seed: str, candidates: List[str], threshold: float = 0.65) -> List[Tuple[str, float]]:
        pairs = self.score(seed, candidates)
        return [(c, s) for c, s in pairs if s >= threshold]
