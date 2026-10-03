import json
import re
from typing import Any


class AIResponseError(ValueError):
    """Raised when an LLM response does not match the expected AI response shape."""


def parse_json_response(raw: str, required_keys: tuple[str, ...]) -> dict[str, Any]:
    text = str(raw or "").strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\\s*```$", "", text).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIResponseError("AI returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise AIResponseError("AI response must be a JSON object")

    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise AIResponseError(f"AI response is missing required fields: {', '.join(missing)}")

    return payload


def _ensure_list(payload: dict[str, Any], key: str) -> None:
    if not isinstance(payload.get(key), list):
        raise AIResponseError(f"AI response field '{key}' must be an array")


def parse_account_response(raw: str) -> dict[str, Any]:
    payload = parse_json_response(raw, (
        "summary", "what_changed", "patterns", "possible_causes",
        "experiments", "metrics_to_monitor",
    ))
    for key in ("what_changed", "patterns", "possible_causes", "experiments", "metrics_to_monitor"):
        _ensure_list(payload, key)
    return payload


def parse_reel_response(raw: str) -> dict[str, Any]:
    payload = parse_json_response(raw, (
        "summary", "working", "possible_weaknesses", "experiments", "metrics_to_monitor",
    ))
    for key in ("working", "possible_weaknesses", "experiments", "metrics_to_monitor"):
        _ensure_list(payload, key)
    return payload


def parse_chat_response(raw: str) -> dict[str, Any]:
    payload = parse_json_response(raw, ("summary", "observations", "hypotheses", "experiments"))
    for key in ("observations", "hypotheses", "experiments"):
        _ensure_list(payload, key)
    return payload
