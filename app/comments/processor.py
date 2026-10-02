import random
import time

from app.comments.service import reply_comment, send_dm
from app.config import REPLY_MESSAGE
from app.database import (
    clear_done,
    get_pending_comments,
    mark_dm_sent,
    mark_done,
    mark_failed,
)
from app.logger import logger


COMMENT_PROCESSING_DELAY_SECONDS = (5, 8)


def _snippet(text, limit=120):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else f"{text[:limit - 3]}..."


def process(media_name: str | None = None, limit: int | None = None):
    if not REPLY_MESSAGE.strip():
        raise RuntimeError(
            "REPLY_MESSAGE is not configured in app/config.py"
        )

    logger.info(
        "Starting queue processing",
        extra={"highlight": "start"},
    )

    comments = get_pending_comments(media_name, limit)

    logger.info(
        "Pending queue size: %d",
        len(comments),
        extra={"highlight": "start"},
    )

    success = 0
    failed = 0
    success_by_media = {}
    failed_by_media = {}
    total = len(comments)

    for index, comment in enumerate(comments, start=1):
        comment_id = comment["comment_id"]
        username = comment["username"]
        text = comment["comment"] or ""
        status = comment["status"]
        queued_media = comment["media_name"]

        logger.info(
            "Processing queued comment %d/%d media=%s comment_id=%s username=%s status=%s retries=%s text=%r",
            index,
            total,
            queued_media,
            comment_id,
            username,
            status,
            comment["retries"],
            _snippet(text),
            extra={"highlight": "progress"},
        )

        if status == "DM_SENT":
            logger.info(
                "Skipping DM send for queued comment %d/%d because DM was already sent comment_id=%s username=%s",
                index,
                total,
                comment_id,
                username,
            )
        else:
            try:
                ok, response = send_dm(comment_id, queued_media)
            except Exception:
                logger.exception(
                    "DM request crashed for queued comment %d/%d media=%s comment_id=%s username=%s",
                    index,
                    total,
                    queued_media,
                    comment_id,
                    username,
                )
                mark_failed(comment_id)
                failed += 1
                failed_by_media[queued_media] = (
                    failed_by_media.get(queued_media, 0) + 1
                )
                continue

            if not ok:
                logger.error(
                    "Skipping public reply for queued comment %d/%d because DM failed media=%s comment_id=%s username=%s response=%s",
                    index,
                    total,
                    queued_media,
                    comment_id,
                    username,
                    response,
                )

                mark_failed(comment_id)
                failed += 1
                failed_by_media[queued_media] = (
                    failed_by_media.get(queued_media, 0) + 1
                )
                continue

            mark_dm_sent(comment_id)

        try:
            reply_comment(comment_id)
            mark_done(comment_id)
            success += 1
            success_by_media[queued_media] = (
                success_by_media.get(queued_media, 0) + 1
            )

            logger.info(
                "Completed queued comment %d/%d media=%s comment_id=%s username=%s",
                index,
                total,
                queued_media,
                comment_id,
                username,
                extra={"highlight": "success"},
            )
        except Exception:
            logger.exception(
                "Public reply failed after DM success for queued comment %d/%d media=%s comment_id=%s username=%s",
                index,
                total,
                queued_media,
                comment_id,
                username,
            )

            mark_failed(comment_id)
            failed += 1
            failed_by_media[queued_media] = (
                failed_by_media.get(queued_media, 0) + 1
            )

        delay = random.uniform(*COMMENT_PROCESSING_DELAY_SECONDS)
        logger.info(
            "Waiting %.1f seconds before processing next comment progress=%d/%d",
            delay,
            index,
            total,
        )
        time.sleep(delay)

    logger.info(
        "Processing summary success=%d failed=%d total=%d",
        success,
        failed,
        total,
        extra={"highlight": "summary"},
    )
    clear_done()

    return {
        "success": success,
        "failed": failed,
        "total": total,
        "success_by_media": success_by_media,
        "failed_by_media": failed_by_media,
    }
