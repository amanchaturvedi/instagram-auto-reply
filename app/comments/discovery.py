from app.comments.service import get_comments, should_reply
from app.config import MY_USERNAME, REPLY_MESSAGE, REPLY_MESSAGES, get_replyable_media
from app.database import enqueue
from app.instagram import get_media_by_id
from app.logger import logger


MY_REPLY_MARKERS = {
    reply.lower()
    for reply in [*REPLY_MESSAGES, REPLY_MESSAGE]
    if reply
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

    processed = set()
    eligible_ids = set()
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
            lower = text.lower()

            if any(marker in lower for marker in MY_REPLY_MARKERS):
                parent = comment.get("parent_id")

                if parent:
                    processed.add(parent)
                    logger.debug(
                        "Detected existing reply marker reply_comment_id=%s parent_comment_id=%s",
                        comment_id,
                        parent,
                    )

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
            eligible_ids.add(comment_id)

            if comment_id not in processed and enqueue(
                comment,
                media_name,
                media_id,
            ):
                discovered += 1
                logger.info(
                    "Discovered reply candidate comment_id=%s username=%s text=%r",
                    comment_id,
                    username,
                    _snippet(text),
                )
        else:
            skipped_no_keyword += 1

        if scanned_user_comments >= fetch_count:
            break

    replied_comments = len(
        eligible_ids.intersection(processed)
    )
    pending_comments = len(eligible_ids) - replied_comments

    total_comments = metadata.get("comments_count")
    if total_comments is None:
        total_comments = len(comments)

    result = {
        "media_name": media_name,
        "media_id": media_id,
        "caption": metadata.get("caption"),
        "timestamp": metadata.get("timestamp"),
        "total_comments": int(total_comments),
        "replied_comments": replied_comments,
        "pending_comments": pending_comments,
        "discovered_comments": discovered,
        "scanned_comments": len(comments),
    }

    logger.info(
        "Discovery completed media=%s total=%d replied=%d pending=%d discovered=%d",
        media_name,
        result["total_comments"],
        result["replied_comments"],
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

    summary = {
        "total_comments": sum(r["total_comments"] for r in results),
        "replied_comments": sum(r["replied_comments"] for r in results),
        "pending_comments": sum(r["pending_comments"] for r in results),
    }

    response = {
        "status": "ok",
        "last_updated": __import__("datetime").datetime.now(
            __import__("zoneinfo").ZoneInfo("Asia/Kolkata")
        ).isoformat(timespec="seconds"),
        "summary": summary,
        "reels": {r["media_name"]: r for r in results},
        "discovered_comments": sum(r["discovered_comments"] for r in results),
        "failed_reels": failed,
    }

    logger.info(
        "Discovery completed all replyable Reels reels=%d failed=%d total=%d replied=%d pending=%d discovered=%d",
        len(results),
        failed,
        summary["total_comments"],
        summary["replied_comments"],
        summary["pending_comments"],
        response["discovered_comments"],
        extra={"highlight": "summary"},
    )

    return response
