ACCOUNT_ANALYSIS_SYSTEM_PROMPT = """You are an Instagram content analytics assistant.
Analyze account-level performance data objectively. Separate observed metrics from hypotheses.
Do not invent missing metrics or claim causation without evidence.
Return concise, actionable insights for a creator.
"""

def build_account_analysis_prompt(context: dict) -> str:
    return f"""Analyze this Instagram account analytics context:

{context}

Return:
1. Account performance summary
2. Strong patterns in the data
3. Weak patterns or possible bottlenecks, clearly labeled as hypotheses
4. Content-level experiments to test next
5. Posting-time observations from the supplied data
6. Metrics worth monitoring
"""
