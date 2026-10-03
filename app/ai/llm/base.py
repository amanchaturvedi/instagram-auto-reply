from abc import ABC, abstractmethod
from typing import Any, Optional


class LLM(ABC):
    """Provider-neutral interface for text generation."""

    @abstractmethod
    def generate(self, prompt: str, system: Optional[str] = None, **kwargs: Any) -> str:
        raise NotImplementedError
