from typing import Any

from app.ai.llm import LLM, get_llm
from app.ai.prompts.chat import CHAT_SYSTEM_PROMPT, build_chat_prompt
from app.ai.schema import parse_chat_response


class ChatAnalyzer:
    """RAG-style chat over deterministic analytics evidence and Reel retrieval."""

    def __init__(self, llm: LLM | None = None) -> None:
        self.llm = llm or get_llm()

    def answer(
        self,
        question: str,
        evidence: dict[str, Any],
        retrieved_reels: list[dict[str, Any]],
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        prompt = build_chat_prompt(
            question=question,
            evidence=evidence,
            retrieved_reels=retrieved_reels,
            history=history or [],
        )
        raw = self.llm.generate(prompt, system=CHAT_SYSTEM_PROMPT)
        return parse_chat_response(raw)
