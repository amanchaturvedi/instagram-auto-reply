from typing import Any

from app.ai.llm import LLM, get_llm
from app.ai.prompts import REEL_ANALYSIS_SYSTEM_PROMPT, build_reel_analysis_prompt


class ReelAnalyzer:
    """AI interpretation layer; depends only on the provider-neutral LLM interface."""

    def __init__(self, llm: LLM | None = None) -> None:
        self.llm = llm or get_llm()

    def analyze(self, reel: dict[str, Any]) -> str:
        return self.llm.generate(build_reel_analysis_prompt(reel), system=REEL_ANALYSIS_SYSTEM_PROMPT)
