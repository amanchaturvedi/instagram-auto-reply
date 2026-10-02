import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from app.comments.service import get_comments, should_reply
from app.config import MEDIA, MY_USERNAME
from app.instagram import get_media_by_id
from app.logger import logger

COMMENTS_FILE = "comments.json"
IST = ZoneInfo("Asia/Kolkata")


def _now_ist():
    return datetime.now(IST).isoformat(timespec="seconds")


def _load_stats():
    if not os.path.exists(COMMENTS_FILE):
        return {
            "last_updated": None,
            "summary": {
                "total_comments": 0,
                "replied_comments": 0,
                "pending_comments": 0,
            },
            "reels": {},
        }

    with open(COMMENTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"{COMMENTS_FILE} must contain a JSON object")

    data.setdefault("last_updated", None)
    data.setdefault(
        "summary",
        {
            "total_comments": 0,
            "replied_comments": 0,
            "pending_comments": 0,
        },
    )
    data.setdefault("reels", {})
    return data


def _save_stats(data):
    temp_file = f"{COMMENTS_FILE}.tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")

    os.replace(temp_file, COMMENTS_FILE)


def _scan_media(media_name, configured_media):
    media_id = configured_media["media_id"]
    metadata = get_media_by_id(media_id)

    comments = list(get_comments(media_id, None))

    replied_parent_ids = set()
    eligible_ids = set()

    for comment in comments:
        comment_id = comment.get("id")
        username = comment.get("from", {}).get("username")
        parent_id = comment.get("parent_id")

        if username == MY_USERNAME and parent_id:
            replied_parent_ids.add(parent_id)

    for comment in comments:
        comment_id = comment.get("id")
        username = comment.get("from", {}).get("username")
        parent_id = comment.get("parent_id")

        if not comment_id or username == MY_USERNAME:
            continue

        if comment.get("hidden", False) or parent_id:
            continue

        if should_reply(comment.get("text") or ""):
            eligible_ids.add(comment_id)

    replied_count = sum(
        1
        for comment_id in eligible_ids
        if comment_id in replied_parent_ids
    )
    pending_count = len(eligible_ids) - replied_count

    total_comments = metadata.get("comments_count")
    if total_comments is None:
        total_comments = len(comments)

    return {
        "media_name": media_name,
        "media_id": media_id,
        "caption": metadata.get("caption"),
        "timestamp": metadata.get("timestamp"),
        "total_comments": int(total_comments),
        "replied_comments": replied_count,
        "pending_comments": pending_count,
        "eligible_comments": len(eligible_ids),
        "scanned_comments": len(comments),
    }


def refresh_comment_stats():
    refreshed_at = _now_ist()

    stats = {
        "last_updated": refreshed_at,
        "summary": {
            "total_comments": 0,
            "replied_comments": 0,
            "pending_comments": 0,
        },
        "reels": {},
    }

    failed = 0

    for media_name, configured_media in MEDIA.items():
        try:
            reel = _scan_media(media_name, configured_media)
            stats["reels"][media_name] = reel

            stats["summary"]["total_comments"] += reel["total_comments"]
            stats["summary"]["replied_comments"] += reel["replied_comments"]
            stats["summary"]["pending_comments"] += reel["pending_comments"]

            logger.info(
                "Comment stats refreshed media=%s total=%d replied=%d pending=%d scanned=%d",
                media_name,
                reel["total_comments"],
                reel["replied_comments"],
                reel["pending_comments"],
                reel["scanned_comments"],
            )
        except Exception:
            failed += 1
            logger.exception(
                "Failed to refresh comment stats media=%s",
                media_name,
            )

    _save_stats(stats)

    logger.info(
        "Comment stats refresh completed reels=%d failed=%d total=%d replied=%d pending=%d",
        len(stats["reels"]),
        failed,
        stats["summary"]["total_comments"],
        stats["summary"]["replied_comments"],
        stats["summary"]["pending_comments"],
        extra={"highlight": "summary"},
    )

    return stats


def get_comment_stats():
    return _load_stats()
