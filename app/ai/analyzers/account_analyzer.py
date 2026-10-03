from typing import Any

from app.ai.llm import LLM, get_llm
from app.ai.schema import parse_account_response
from app.ai.prompts.account_analysis import (
    ACCOUNT_ANALYSIS_SYSTEM_PROMPT,
    build_account_analysis_prompt,
)


class AccountAnalyzer:
    """AI interpretation layer over deterministic account evidence."""

    def __init__(self, llm: LLM | None = None) -> None:
        self.llm = llm or get_llm()

    def analyze(self, evidence: dict[str, Any]) -> dict[str, Any]:
        raw = self.llm.generate(
            build_account_analysis_prompt(evidence),
            system=ACCOUNT_ANALYSIS_SYSTEM_PROMPT,
        )
        return parse_account_response(raw)
