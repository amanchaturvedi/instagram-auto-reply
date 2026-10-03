import json
from app.insights.collector import _load_insights, _save_insights
from app.instagram import get_media
from app.logger import logger
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def refresh_reel_catalog():
    data = _load_insights()

    added = 0
    updated = 0
    skipped = 0

    # Always paginate through the complete media response. Previously this
    # passed known IDs as stop_ids, which could stop pagination as soon as an
    # already-known Reel appeared on an older page and hide all older Reels.
    for media in get_media():
        if media.get("media_product_type") != "REELS":
            skipped += 1
            continue

        media_id = media.get("id")
        if not media_id:
            skipped += 1
            continue

        reel = data["reels"].get(media_id)

        if reel is None:
            data["reels"][media_id] = {
                "media_id": media_id,
                "caption": media.get("caption"),
                "media_type": media.get("media_type"),
                "media_product_type": media.get("media_product_type"),
                "timestamp": media.get("timestamp"),
                "comments_count": media.get("comments_count"),
                "snapshots": [],
            }
            added += 1
            continue

        changed = False

        for key in (
            "caption",
            "media_type",
            "media_product_type",
            "timestamp",
            "comments_count",
        ):
            value = media.get(key)

            if value is not None and reel.get(key) != value:
                reel[key] = value
                changed = True

        if changed:
            updated += 1

    data["catalog_last_updated"] = datetime.now(IST).isoformat(timespec="seconds")
    _save_insights(data)

    logger.info(
        "Reel catalog refresh completed added=%d updated=%d total=%d skipped=%d",
        added,
        updated,
        len(data["reels"]),
        skipped,
        extra={"highlight": "summary"},
    )

    return {
        "status": "ok",
        "added": added,
        "updated": updated,
        "total_reels": len(data["reels"]),
        "skipped": skipped,
    }
