import re
from collections import Counter

from app.analytics.analyzer import _latest_snapshot, load_analysis_reels
from app.analytics.metrics import enrich_reel_metrics
from app.analytics.posting_time import posting_features, select_snapshot_at_age

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9']{2,}")
STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "have", "just",
    "your", "you", "was", "are", "but", "not", "its", "into", "about",
    "when", "where", "what", "how", "which", "reel", "reels", "instagram",
    "content", "show", "find", "give", "tell", "my", "me", "to", "of",
}


def _tokens(text):
    return {
        token.lower()
        for token in TOKEN_RE.findall(str(text or ""))
        if token.lower() not in STOPWORDS
    }


def _row(reel):
    latest = _latest_snapshot(reel)
    latest_metrics = enrich_reel_metrics(
        latest.get("metrics") if latest else {}
    )
    age = select_snapshot_at_age(reel)
    age_metrics = None
    if age:
        age_metrics = enrich_reel_metrics(
            age["snapshot"].get("metrics")
        )

    posting = posting_features(reel.get("timestamp"))
    return {
        "media_id": reel.get("media_id"),
        "caption": (reel.get("caption") or "").strip(),
        "timestamp": reel.get("timestamp"),
        "posting": posting,
        "latest_metrics": latest_metrics,
        "24h_metrics": age_metrics,
        "24h_age_hours": age.get("age_hours") if age else None,
    }


def retrieve_reels(query, limit=6, reels=None):
    if reels is None:
        reels = load_analysis_reels()

    query_tokens = _tokens(query)
    rows = [_row(reel) for reel in reels]
    scored = []

    for row in rows:
        caption_tokens = _tokens(row["caption"])
        score = len(query_tokens & caption_tokens) * 4

        query_lower = str(query).lower()
        caption_lower = row["caption"].lower()

        if any(word in query_lower for word in ("best", "top", "perform")):
            score += min(float(row["latest_metrics"].get("views") or 0) / 10000, 5)
        if any(word in query_lower for word in ("save", "saved")):
            score += min(float(row["latest_metrics"].get("saved") or 0) / 20, 5)
        if any(word in query_lower for word in ("share", "shared")):
            score += min(float(row["latest_metrics"].get("shares") or 0) / 20, 5)
        if any(word in query_lower for word in ("engagement", "engage")):
            score += min(float(row["latest_metrics"].get("interaction_rate") or 0), 5)

        if not query_tokens and not caption_lower:
            continue

        if score > 0:
            scored.append((score, row))

    scored.sort(key=lambda item: item[0], reverse=True)

    return [
        {
            "rank": index + 1,
            **row,
        }
        for index, (_, row) in enumerate(scored[:limit])
    ]
