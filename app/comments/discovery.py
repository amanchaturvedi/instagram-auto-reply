from app.comments.service import REPLIES, get_comments, should_reply
from app.config import MEDIA, MY_USERNAME
from app.database import enqueue
from app.logger import logger


MY_REPLY_MARKERS = {reply.lower() for reply in REPLIES}


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

    media_id = MEDIA[media_name]["media_id"]

    try:
        comments = list(get_comments(media_id, fetch_count))
    except Exception:
        logger.exception(
            "Discovery failed while fetching comments fetch_count=%d",
            fetch_count,
        )
        raise

    if not comments:
        logger.info("Discovery finished: no comments found")
        return

    logger.info("Discovery loaded comments=%d", len(comments))

    processed = set()
    discovered = 0
    scanned_user_comments = 0
    skipped_own_reply = 0
    skipped_nested = 0
    skipped_already_replied = 0
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
            logger.debug(
                "Skipped hidden comment comment_id=%s username=%s text=%r",
                comment_id,
                username,
                _snippet(text),
            )
            continue

        if parent_id:
            skipped_nested += 1
            logger.debug(
                "Skipped nested comment comment_id=%s parent_comment_id=%s username=%s text=%r",
                comment_id,
                parent_id,
                username,
                _snippet(text),
            )
            continue

        scanned_user_comments += 1

        if should_reply(text):
            if comment_id not in processed:
                if enqueue(comment, media_name, media_id):
                    discovered += 1
                    logger.info(
                        "Discovered reply candidate comment_id=%s username=%s text=%r",
                        comment_id,
                        username,
                        _snippet(text),
                    )
            else:
                skipped_already_replied += 1
                logger.debug(
                    "Skipped comment with existing reply comment_id=%s username=%s",
                    comment_id,
                    username,
                )
        else:
            skipped_no_keyword += 1
            logger.debug(
                "Skipped comment without trigger keyword comment_id=%s username=%s text=%r",
                comment_id,
                username,
                _snippet(text),
            )

        if scanned_user_comments >= fetch_count:
            logger.info(
                "Scanned requested user comment count=%d raw_comments_loaded=%d",
                scanned_user_comments,
                len(comments),
            )
            break

    logger.info(
        "Discovery completed for media=%s discovered=%d scanned_top_level_user_comments=%d skipped_own=%d skipped_nested=%d skipped_already_replied=%d skipped_no_keyword=%d skipped_hidden=%d",
        media_name,
        discovered,
        scanned_user_comments,
        skipped_own_reply,
        skipped_nested,
        skipped_already_replied,
        skipped_no_keyword,
        skipped_hidden,
        extra={"highlight": "summary"},
    )


def discover_all(fetch_count: int):
    logger.info(
        "Starting discovery for %d media",
        len(MEDIA),
        extra={"highlight": "start"},
    )

    for media_name, media in MEDIA.items():
        logger.info(
            "Discovering media=%s media_id=%s",
            media_name,
            media["media_id"],
        )

        try:
            discover(media_name, fetch_count)
        except Exception:
            logger.exception(
                "Discovery failed media=%s",
                media_name,
            )

    logger.info(
        "Discovery completed for all media",
        extra={"highlight": "summary"},
    )
