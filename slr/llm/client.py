# slr/llm/client.py
import os
import time
from typing import Optional
from openai import OpenAI, APIStatusError

_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://kiste.informatik.tu-chemnitz.de/v1")

def _get_api_key() -> str:
    key = os.getenv("KISTE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Set env var KISTE_API_KEY with your API key")
    return key

class LLMClient:
    def __init__(self, model: str = "gpt-oss-120b", api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.model = model
        self.api_key = api_key or _get_api_key()
        self.base_url = base_url or _BASE_URL
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(self, system: str, user: str, max_retries: int = 4, request_timeout: float = 60.0) -> str:
        """Chat with retries for flaky upstream (502/503/504)."""
        delay = 1.0
        for attempt in range(max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.2,         # stable taxonomy
                    stream=False,
                    timeout=request_timeout, # httpx param
                )
                return resp.choices[0].message.content or ""
            except APIStatusError as e:
                code = getattr(e, "status_code", None)
                if code in (502, 503, 504):
                    time.sleep(delay)
                    delay = min(delay * 2, 8)
                    continue
                raise
            except Exception:
                # network hiccup or timeout
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    delay = min(delay * 2, 8)
                    continue
                raise
