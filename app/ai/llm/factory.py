import os
from typing import Any

from .base import LLM
from .ollama_llm import OllamaLLM


class UnsupportedLLMProvider(ValueError):
    pass


def get_llm(provider: str | None = None, **kwargs: Any) -> LLM:
    selected = (provider or os.getenv("LLM_PROVIDER", "ollama")).strip().lower()
    if selected == "ollama":
        return OllamaLLM(**kwargs)
    raise UnsupportedLLMProvider(f"Unsupported LLM_PROVIDER={selected!r}. Available providers: ollama")
