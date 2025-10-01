# slr/llm/client.py
from __future__ import annotations
import os
from typing import Optional
from openai import OpenAI

BASE_URL = "https://kiste.informatik.tu-chemnitz.de/v1"
MODEL = "glm-4.5-air"  # professor: only use this model

def _get_api_key() -> str:
    key = os.getenv("KISTE_API_KEY")
    if not key:
        raise RuntimeError("Set env var KISTE_API_KEY with your API key")
    return key

class LLMClient:
    """
    Minimal wrapper for an OpenAI-compatible endpoint.
    IMPORTANT: no temperature / no max_tokens (per professor).
    """
    def __init__(self,
                 api_key: Optional[str] = None,
                 base_url: str = BASE_URL,
                 model: str = MODEL):
        self.api_key = api_key or _get_api_key()
        self.client = OpenAI(api_key=self.api_key, base_url=base_url)
        self.model = model

    def chat(self, system: str, user: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}]
            # NOTE: no temperature, no max_tokens
        )
        return resp.choices[0].message.content.strip()
