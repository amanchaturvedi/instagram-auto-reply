import re
from app.analytics.analyzer import _latest_snapshot, load_analysis_reels
from app.analytics.metrics import enrich_reel_metrics
from app.analytics.posting_time import posting_features, select_snapshot_at_age

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9']{2,}")
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

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


def _recent_limit(query, default_limit):
    query_lower = str(query or "").lower()

    match = re.search(
        r"\b(?:last|latest|newest|most recent)\s+(?:(\d+)\s+|(one|two|three|four|five|six|seven|eight|nine|ten)\s+)?(?:reels?|posts?)\b",
        query_lower,
    )
    if match:
        if match.group(1):
            return max(1, min(int(match.group(1)), 50))
        if match.group(2):
            return NUMBER_WORDS[match.group(2)]
        return default_limit

    if re.search(r"\b(?:latest|newest|recent)\b", query_lower):
        return default_limit

    return None


def _timestamp_sort_key(value):
    return str(value or "")


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

    recent_limit = _recent_limit(query, limit)
    if recent_limit is not None:
        recent_rows = sorted(
            rows,
            key=lambda row: _timestamp_sort_key(row.get("timestamp")),
            reverse=True,
        )[:recent_limit]
        return [
            {
                "rank": index + 1,
                **row,
            }
            for index, row in enumerate(recent_rows)
        ]

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
