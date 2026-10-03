"""Build compact, deterministic evidence for AI interpretation.

The LLM should interpret this evidence rather than calculate metrics from raw Reel data.
"""

import re
from collections import Counter, defaultdict
from datetime import datetime

from .analyzer import _latest_snapshot, load_analysis_reels
from .metrics import enrich_reel_metrics
from .posting_time import posting_features, select_snapshot_at_age

MIN_GROUP_SIZE = 3
RECENT_COUNT = 10
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9']{2,}")


def _percentile(values, fraction):
    values = sorted(float(value) for value in values if value is not None)
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 3)
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return round(values[lower] + (values[upper] - values[lower]) * weight, 3)


def _summary(values):
    values = [float(value) for value in values if value is not None]
    if not values:
        return {"count": 0, "median": None, "p25": None, "p75": None}
    return {
        "count": len(values),
        "median": _percentile(values, 0.50),
        "p25": _percentile(values, 0.25),
        "p75": _percentile(values, 0.75),
    }


def _pct_change(current, previous):
    if current is None or previous in (None, 0):
        return None
    return round(((current - previous) / previous) * 100, 2)


def _reel_row(reel, source="latest"):
    latest = _latest_snapshot(reel)
    latest_metrics = enrich_reel_metrics(
        latest.get("metrics") if latest else {}
    )
    age = select_snapshot_at_age(reel)

    if source == "24h" and age:
        snapshot = age["snapshot"]
        metrics = enrich_reel_metrics(snapshot.get("metrics"))
        age_hours = age["age_hours"]
        collected_at = snapshot.get("collected_at")
    else:
        metrics = latest_metrics
        age_hours = None
        collected_at = latest.get("collected_at") if latest else None

    posting = posting_features(reel.get("timestamp"))
    return {
        "media_id": reel.get("media_id"),
        "caption": (reel.get("caption") or "").strip(),
        "timestamp": reel.get("timestamp"),
        "collected_at": collected_at,
        "age_hours": age_hours,
        "posting": posting,
        "metrics": metrics,
        "has_24h_snapshot": age is not None,
    }


def _metric_snapshot(rows, metric):
    return _summary([row["metrics"].get(metric) for row in rows])


def _select_source(reels):
    rows_24h = [_reel_row(reel, "24h") for reel in reels]
    covered = sum(row["has_24h_snapshot"] for row in rows_24h)
    if covered >= max(MIN_GROUP_SIZE * 2, int(len(reels) * 0.25)):
        return "24h"
    return "latest"


def _ranked_reels(rows, metric, limit=5, reverse=True):
    candidates = [
        row for row in rows
        if row["metrics"].get(metric) is not None
    ]
    candidates.sort(
        key=lambda row: float(row["metrics"].get(metric)),
        reverse=reverse,
    )
    return [
        {
            "media_id": row["media_id"],
            "caption": row["caption"][:140],
            "posted_at": row["timestamp"],
            "value": row["metrics"].get(metric),
            "metric": metric,
            "source": "24h" if row["age_hours"] is not None else "latest",
        }
        for row in candidates[:limit]
    ]


def _posting_groups(rows, key):
    groups = defaultdict(list)
    for row in rows:
        posting = row.get("posting") or {}
        value = posting.get(key)
        if value is not None:
            groups[value].append(row)

    result = []
    for group, items in groups.items():
        if len(items) < MIN_GROUP_SIZE:
            continue
        result.append({
            "group": group,
            "n": len(items),
            "median_views": _summary(
                [r["metrics"].get("views") for r in items]
            )["median"],
            "median_reach": _summary(
                [r["metrics"].get("reach") for r in items]
            )["median"],
            "median_engagement_rate": _summary(
                [r["metrics"].get("interaction_rate") for r in items]
            )["median"],
        })

    result.sort(
        key=lambda item: (
            item["median_views"] is not None,
            item["median_views"] or 0,
        ),
        reverse=True,
    )
    return result


_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "have", "just",
    "your", "you", "was", "are", "but", "not", "its", "into", "about",
    "when", "where", "what", "how", "only", "more", "one", "out", "all",
    "new", "get", "got", "our", "has", "had", "via", "india", "reel",
    "travel", "trip", "instagram", "explore", "like", "follow", "comment",
    "location", "dm", "https", "www",
}


def _caption_keyword_evidence(rows):
    groups = defaultdict(list)
    for row in rows:
        tokens = {
            token.lower()
            for token in TOKEN_RE.findall(row["caption"])
            if token.lower() not in _STOPWORDS
        }
        for token in tokens:
            groups[token].append(row)

    result = []
    for keyword, items in groups.items():
        if len(items) < MIN_GROUP_SIZE:
            continue
        result.append({
            "keyword": keyword,
            "n": len(items),
            "median_views": _summary(
                [r["metrics"].get("views") for r in items]
            )["median"],
            "median_reach": _summary(
                [r["metrics"].get("reach") for r in items]
            )["median"],
            "median_engagement_rate": _summary(
                [r["metrics"].get("interaction_rate") for r in items]
            )["median"],
        })

    result.sort(
        key=lambda item: item["n"],
        reverse=True,
    )
    return result[:20]


def _posting_frequency(reels):
    dates = []
    for reel in reels:
        posting = posting_features(reel.get("timestamp"))
        if posting:
            dates.append(datetime.fromisoformat(posting["posted_at"]))
    dates.sort()
    if len(dates) < 2:
        return {"reels_with_timestamps": len(dates)}

    gaps = [
        (dates[index] - dates[index - 1]).total_seconds() / 86400
        for index in range(1, len(dates))
    ]
    return {
        "reels_with_timestamps": len(dates),
        "median_days_between_reels": round(_percentile(gaps, 0.5), 2),
        "p25_days_between_reels": round(_percentile(gaps, 0.25), 2),
        "p75_days_between_reels": round(_percentile(gaps, 0.75), 2),
    }


def build_account_evidence(reels=None):
    if reels is None:
        reels = load_analysis_reels()

    reels = list(reels)
    source = _select_source(reels)

    rows = [_reel_row(reel, source) for reel in reels]
    rows.sort(key=lambda row: row.get("timestamp") or "", reverse=True)

    rows_with_24h = [row for row in rows if row["has_24h_snapshot"]]
    source_rows = rows if source == "latest" else rows_with_24h

    recent = source_rows[:RECENT_COUNT]
    previous = source_rows[RECENT_COUNT:RECENT_COUNT * 2]

    recent_vs_history = {
        "metric_source": source,
        "recent_count": len(recent),
        "previous_count": len(previous),
    }

    for metric in (
        "views",
        "reach",
        "interaction_rate",
        "skip_rate",
        "avg_watch_time_ms",
    ):
        recent_value = _summary(
            [row["metrics"].get(metric) for row in recent]
        )["median"]
        previous_value = _summary(
            [row["metrics"].get(metric) for row in previous]
        )["median"]
        recent_vs_history[metric] = {
            "recent_median": recent_value,
            "previous_median": previous_value,
            "change_percent": _pct_change(recent_value, previous_value),
        }

    summary_metrics = (
        "views",
        "reach",
        "interaction_rate",
        "like_rate",
        "comment_rate",
        "share_rate",
        "save_rate",
        "skip_rate",
        "avg_watch_time_ms",
    )

    account_summary = {
        metric: _metric_snapshot(source_rows, metric)
        for metric in summary_metrics
    }

    return {
        "dataset": {
            "reels_analyzed": len(reels),
            "reels_with_latest_snapshot": sum(
                1 for reel in reels if _latest_snapshot(reel) is not None
            ),
            "reels_with_24h_snapshot": len(rows_with_24h),
            "analysis_metric_source": source,
            "min_group_size": MIN_GROUP_SIZE,
        },
        "account_summary": account_summary,
        "recent_vs_history": recent_vs_history,
        "top_reels": {
            "views": _ranked_reels(source_rows, "views"),
            "reach": _ranked_reels(source_rows, "reach"),
            "engagement_rate": _ranked_reels(source_rows, "interaction_rate"),
            "shares": _ranked_reels(source_rows, "shares"),
            "saves": _ranked_reels(source_rows, "saved"),
        },
        "bottom_reels": {
            "views": _ranked_reels(source_rows, "views", reverse=False),
            "engagement_rate": _ranked_reels(
                source_rows, "interaction_rate", reverse=False
            ),
        },
        "posting_time_evidence": {
            "by_hour": _posting_groups(source_rows, "hour"),
            "by_slot": _posting_groups(source_rows, "slot"),
            "by_weekday": _posting_groups(source_rows, "day_of_week"),
        },
        "caption_keyword_evidence": _caption_keyword_evidence(source_rows),
        "posting_frequency": _posting_frequency(reels),
        "recent_reels": [
            {
                "media_id": row["media_id"],
                "caption": row["caption"][:140],
                "posted_at": row["timestamp"],
                "views": row["metrics"].get("views"),
                "reach": row["metrics"].get("reach"),
                "engagement_rate": row["metrics"].get("interaction_rate"),
                "skip_rate": row["metrics"].get("skip_rate"),
                "avg_watch_time_ms": row["metrics"].get("avg_watch_time_ms"),
            }
            for row in recent
        ],
    }
