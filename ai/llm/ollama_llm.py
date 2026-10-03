from typing import Any, Optional

import requests

from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from .base import LLM


class OllamaLLM(LLM):
    """Local Ollama provider using Ollama's HTTP API."""

    def __init__(self, model: str = OLLAMA_MODEL, base_url: str = OLLAMA_BASE_URL, timeout: int = 120) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(self, prompt: str, system: Optional[str] = None, **kwargs: Any) -> str:
        payload = {"model": self.model, "prompt": prompt, "stream": False, "options": kwargs}
        if system:
            payload["system"] = system
        response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
        response.raise_for_status()
        body = response.json()
        result = body.get("response")
        if not isinstance(result, str):
            raise RuntimeError(f"Unexpected Ollama response: {body}")
        return result.strip()
