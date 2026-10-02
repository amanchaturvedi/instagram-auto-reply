import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from app.instagram import REEL_INSIGHT_METRICS, get_media, get_media_by_id, get_media_insights
from app.logger import logger

INSIGHTS_FILE = "insights.json"
IST = ZoneInfo("Asia/Kolkata")


def _now_ist():
    return datetime.now(IST).isoformat(timespec="seconds")


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


def _save_insights(data):
    temp_file = f"{INSIGHTS_FILE}.tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")

    os.replace(temp_file, INSIGHTS_FILE)


def _metric_value(metric):
    values = metric.get("values", [])
    if not values:
        return None
    return values[0].get("value")


def _normalize_metrics(api_response):
    normalized = {}

    for metric in api_response.get("data", []):
        name = metric.get("name")
        if not name:
            continue

        value = _metric_value(metric)

        if name == "ig_reels_avg_watch_time":
            normalized["avg_watch_time_ms"] = value
        elif name == "ig_reels_video_view_total_time":
            normalized["total_watch_time_ms"] = value
        elif name == "reels_skip_rate":
            normalized["skip_rate"] = value
        else:
            normalized[name] = value

    return normalized


def _upsert_reel(data, media):
    media_id = media["id"]

    reel = data["reels"].setdefault(
        media_id,
        {
            "media_id": media_id,
            "caption": media.get("caption"),
            "media_type": media.get("media_type"),
            "media_product_type": media.get("media_product_type"),
            "timestamp": media.get("timestamp"),
            "snapshots": [],
        },
    )

    for key in (
        "caption",
        "media_type",
        "media_product_type",
        "timestamp",
    ):
        if media.get(key) is not None:
            reel[key] = media[key]

    return reel


def _append_snapshot(reel, collected_at, metrics):
    snapshot = {
        "collected_at": collected_at,
        "metrics": metrics,
    }

    snapshots = reel.setdefault("snapshots", [])

    for existing in snapshots:
        if existing.get("collected_at") == collected_at:
            existing.update(snapshot)
            return False

    snapshots.append(snapshot)
    return True


def _get_media_items(media_id=None):
    if media_id:
        return [get_media_by_id(media_id)]

    return list(get_media())


def collect_reel_insights(media_id=None):
    data = _load_insights()
    collected_at = _now_ist()

    collected = 0
    skipped = 0
    failed = 0

    for media in _get_media_items(media_id):
        current_id = media.get("id")

        if not current_id:
            skipped += 1
            logger.warning("Skipping media without id")
            continue

        if media.get("media_product_type") != "REELS":
            skipped += 1
            logger.info(
                "Skipping non-Reel media_id=%s media_product_type=%s",
                current_id,
                media.get("media_product_type"),
            )
            continue

        reel = _upsert_reel(data, media)

        try:
            api_response = get_media_insights(
                current_id,
                REEL_INSIGHT_METRICS,
            )
            metrics = _normalize_metrics(api_response)

            added = _append_snapshot(
                reel,
                collected_at,
                metrics,
            )

            if added:
                collected += 1

            logger.info(
                "Saved insights snapshot media_id=%s metrics=%d new=%s",
                current_id,
                len(metrics),
                added,
            )

        except Exception:
            failed += 1
            logger.exception(
                "Failed to collect insights media_id=%s",
                current_id,
            )

    data["last_updated"] = collected_at
    _save_insights(data)

    logger.info(
        "Insights collection completed collected=%d skipped=%d failed=%d file=%s",
        collected,
        skipped,
        failed,
        INSIGHTS_FILE,
        extra={"highlight": "summary"},
    )

    return data
