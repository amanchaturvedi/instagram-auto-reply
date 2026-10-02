from datetime import datetime
from zoneinfo import ZoneInfo

from app.comments.service import get_comments, should_reply
from app.config import get_replyable_media, MY_USERNAME
from app.database import enqueue, get_pending_count_by_media
from app.instagram import get_media_by_id
from app.logger import logger


MY_REPLY_MARKERS = {
    "please check dm",
    "please check your dm",
    "shared the location in dm",
    "i've sent you the location in dm",
    "location sent! check your dm",
    "sent you the location",
}


def _snippet(text, limit=120):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else f"{text[:limit - 3]}..."


def discover(media_name: str, fetch_count: int):
    logger.info(
        "Starting discovery media_name=%s fetch_count=%d my_username=%s",
        media_name,
        fetch_count,
        MY_USERNAME,
        extra={"highlight": "start"},
    )

    configured_media = get_replyable_media()[media_name]
    media_id = configured_media["media_id"]

    try:
        metadata = get_media_by_id(media_id)
        comments = list(get_comments(media_id, fetch_count))
    except Exception:
        logger.exception(
            "Discovery failed media=%s fetch_count=%d",
            media_name,
            fetch_count,
        )
        raise

    # Build the set in a first pass so a bot reply appearing after its
    # parent comment in the API response is still recognized.
    bot_replied_to = {
        comment.get("parent_id")
        for comment in comments
        if comment.get("from", {}).get("username") == MY_USERNAME
        and comment.get("parent_id")
        and any(
            marker in (comment.get("text") or "").lower()
            for marker in MY_REPLY_MARKERS
        )
    }

    discovered = 0
    scanned_user_comments = 0
    skipped_own_reply = 0
    skipped_nested = 0
    skipped_no_keyword = 0
    skipped_hidden = 0

    for comment in comments:
        comment_id = comment["id"]
        username = comment.get("from", {}).get("username")
        parent_id = comment.get("parent_id")
        hidden = comment.get("hidden", False)
        text = comment.get("text") or ""

        if username == MY_USERNAME:
            skipped_own_reply += 1
            continue

        if hidden:
            skipped_hidden += 1
            continue

        if parent_id:
            skipped_nested += 1
            continue

        scanned_user_comments += 1

        if should_reply(text):
            if comment_id in bot_replied_to:
                continue

            if enqueue(comment, media_name, media_id):
                discovered += 1
                logger.info(
                    "Discovered pending comment_id=%s username=%s text=%r",
                    comment_id,
                    username,
                    _snippet(text),
                )
        else:
            skipped_no_keyword += 1

        if scanned_user_comments >= fetch_count:
            break

    pending_count = get_pending_count_by_media([media_id]).get(media_id, 0)
    last_updated = datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).isoformat(timespec="seconds")

    result = {
        "media_name": media_name,
        "media_id": media_id,
        "caption": metadata.get("caption"),
        "timestamp": metadata.get("timestamp"),
        "pending_comments": pending_count,
        "discovered_comments": discovered,
        "scanned_comments": len(comments),
        "last_updated": last_updated,
    }

    logger.info(
        "Discovery completed media=%s pending=%d discovered=%d",
        media_name,
        result["pending_comments"],
        result["discovered_comments"],
        extra={"highlight": "summary"},
    )

    return result


def discover_all(fetch_count: int):
    replyable_media = get_replyable_media()

    logger.info(
        "Starting discovery for %d replyable Reels",
        len(replyable_media),
        extra={"highlight": "start"},
    )

    results = []
    failed = 0

    for media_name in replyable_media:
        try:
            results.append(discover(media_name, fetch_count))
        except Exception:
            failed += 1
            logger.exception(
                "Discovery failed media=%s",
                media_name,
            )

    last_updated = datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).isoformat(timespec="seconds")

    return {
        "status": "ok",
        "last_updated": last_updated,
        "reels": {
            result["media_name"]: result
            for result in results
        },
        "discovered_comments": sum(
            result["discovered_comments"]
            for result in results
        ),
        "failed_reels": failed,
    }
