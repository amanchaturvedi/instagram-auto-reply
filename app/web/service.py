import json
import os
from datetime import datetime

from app.config import IG_USER_ID, MY_USERNAME

INSIGHTS_FILE = "insights.json"


def _load_insights():
    if not os.path.exists(INSIGHTS_FILE):
        return {"last_updated": None, "reels": {}}

    with open(INSIGHTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"{INSIGHTS_FILE} must contain a JSON object")

    data.setdefault("last_updated", None)
    data.setdefault("reels", {})
    return data


def _latest_snapshot(reel):
    snapshots = reel.get("snapshots", [])

    if not snapshots:
        return None

    return max(
        snapshots,
        key=lambda snapshot: snapshot.get("collected_at", ""),
    )


def _format_reel(reel):
    snapshot = _latest_snapshot(reel) or {}
    metrics = snapshot.get("metrics", {})

    reach = metrics.get("reach")
    total_interactions = metrics.get("total_interactions")

    engagement_rate = None
    if total_interactions is not None and reach:
        engagement_rate = round((total_interactions / reach) * 100, 2)

    avg_watch_ms = metrics.get("avg_watch_time_ms")
    total_watch_ms = metrics.get("total_watch_time_ms")

    return {
        "media_id": reel.get("media_id"),
        "caption": reel.get("caption"),
        "media_type": reel.get("media_type"),
        "media_product_type": reel.get("media_product_type"),
        "timestamp": reel.get("timestamp"),
        "last_collected_at": snapshot.get("collected_at"),
        "metrics": {
            **metrics,
            "engagement_rate": engagement_rate,
            "avg_watch_time_seconds": (
                round(avg_watch_ms / 1000, 3)
                if avg_watch_ms is not None
                else None
            ),
            "total_watch_time_hours": (
                round(total_watch_ms / 3_600_000, 2)
                if total_watch_ms is not None
                else None
            ),
        },
    }


def get_reels():
    data = _load_insights()

    reels = [
        _format_reel(reel)
        for reel in data["reels"].values()
    ]

    reels.sort(
        key=lambda reel: reel.get("timestamp") or "",
        reverse=True,
    )

    return reels


def get_reel(media_id):
    data = _load_insights()
    reel = data["reels"].get(media_id)

    if reel is None:
        return None

    return _format_reel(reel)


def get_dashboard_summary():
    data = _load_insights()
    reels = [
        _format_reel(reel)
        for reel in data["reels"].values()
    ]

    total_views = sum(
        (reel["metrics"].get("views") or 0)
        for reel in reels
    )

    return {
        "account": {
            "instagram_user_id": IG_USER_ID,
            "username": MY_USERNAME,
        },
        "last_updated": data.get("last_updated"),
        "reels_tracked": len(reels),
        "total_views": total_views,
    }


def health_check():
    return {
        "status": "ok",
        "insights_file_exists": os.path.exists(INSIGHTS_FILE),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
