REEL_ANALYSIS_SYSTEM_PROMPT = """You are an Instagram content analytics assistant.
Analyze performance data objectively. Separate observed metrics from hypotheses.
Do not invent missing metrics. Return concise, actionable insights for a creator.
"""


def build_reel_analysis_prompt(reel: dict) -> str:
    return f"""Analyze this Instagram Reel performance data:\n\n{reel}\n\nReturn:\n1. Performance summary\n2. What appears to be working\n3. Potential reasons for weak performance, clearly labeled as hypotheses\n4. Content-level experiments to test next\n5. Metrics worth monitoring\n"""
