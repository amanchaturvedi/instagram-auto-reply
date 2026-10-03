REEL_ANALYSIS_SYSTEM_PROMPT = """You are an Instagram content analytics assistant.
Analyze performance data objectively. Separate observed metrics from hypotheses.
Do not invent missing metrics. Return concise, actionable insights for a creator. Return ONLY valid JSON, with no Markdown fences.
"""


def build_reel_analysis_prompt(reel: dict) -> str:
    return (
        "Analyze this Instagram Reel performance data:\n\n"
        + str(reel)
        + "\n\nReturn exactly this JSON shape:\n"
        + '{"summary":"...","working":[{"title":"...","detail":"..."}],'
        + '"possible_weaknesses":[{"title":"...","detail":"..."}],'
        + '"experiments":[{"test":"...","why":"...","metric":"..."}],'
        + '"metrics_to_monitor":["..."]}'
    )
