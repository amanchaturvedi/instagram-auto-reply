REEL_ANALYSIS_SYSTEM_PROMPT = """You are an Instagram content analytics assistant.
Analyze performance data objectively. Separate observed metrics from hypotheses.
Do not invent missing metrics. Return concise, actionable insights for a creator. Return ONLY valid JSON, with no Markdown fences.
"""


def build_reel_analysis_prompt(reel: dict) -> str:
    return f"""Analyze this Instagram Reel performance data:\n\n{reel}\n\nReturn exactly this JSON shape:\n{\n  "summary": "...",\n  "working": [{"title": "...", "detail": "..."}],\n  "possible_weaknesses": [{"title": "...", "detail": "..."}],\n  "experiments": [{"test": "...", "why": "...", "metric": "..."}],\n  "metrics_to_monitor": ["..."]\n}\n"""
