from typing import Any

from ai.llm import LLM, get_llm
from ai.prompts.account_analysis import (
    ACCOUNT_ANALYSIS_SYSTEM_PROMPT,
    build_account_analysis_prompt,
)


class AccountAnalyzer:
    """AI interpretation layer over deterministic account evidence."""

    def __init__(self, llm: LLM | None = None) -> None:
        self.llm = llm or get_llm()

    def analyze(self, evidence: dict[str, Any]) -> str:
        return self.llm.generate(
            build_account_analysis_prompt(evidence),
            system=ACCOUNT_ANALYSIS_SYSTEM_PROMPT,
        )
