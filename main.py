import json

from config import MEDIA, MY_USERNAME
from instagram import (
    REPLIES,
    get_comments,
    get_media,
    reply_comment,
    send_dm,
    should_reply,
)

from database import (
    enqueue,
    get_pending_comments,
    mark_dm_sent,
    mark_done,
    mark_failed,
    clear_done
)

import random
import time
import argparse
import sys

from logger import logger

MY_REPLY_MARKERS = {reply.lower() for reply in REPLIES}
COMMENT_PROCESSING_DELAY_SECONDS = (5, 8)
DISCOVERY_FETCH_MULTIPLIER = 5
DISCOVER_DEFAULT = 100
PROCESS_DEFAULT = 10


def _snippet(text, limit=120):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else f"{text[:limit - 3]}..."


def discover(media_name: str, fetch_count: int):
    logger.info("Starting discovery media_name=%s fetch_count=%d my_username=%s", media_name, fetch_count, MY_USERNAME, extra={"highlight": "start"})
    
    media_id = MEDIA[media_name]["media_id"]

    try:
        comments = list(get_comments(media_id, fetch_count))
    except Exception:
        logger.exception("Discovery failed while fetching comments fetch_count=%d", fetch_count)
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

        # My replies
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

        # User comments
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
        "Discovery completed discovered=%d scanned_top_level_user_comments=%d skipped_own=%d skipped_nested=%d skipped_already_replied=%d skipped_no_keyword=%d skipped_hidden=%d",
        discovered,
        scanned_user_comments,
        skipped_own_reply,
        skipped_nested,
        skipped_already_replied,
        skipped_no_keyword,
        skipped_hidden,
        extra={"highlight": "summary"},
    )


def process(media_name: str,limit: int | None = None):
    logger.info("Starting queue processing", extra={"highlight": "start"})

    comments = get_pending_comments(media_name, limit)

    logger.info("Pending queue size: %d", len(comments), extra={"highlight": "start"})

    success = 0
    failed = 0
    total = len(comments)

    for index, comment in enumerate(comments, start=1):

        comment_id = comment["comment_id"]
        username = comment["username"]
        text = comment["comment"] or ""
        status = comment["status"]

        logger.info(
            "Processing queued comment %d/%d comment_id=%s username=%s status=%s retries=%s text=%r",
            index,
            total,
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
                ok, response = send_dm(comment_id, media_name)
            except Exception:
                logger.exception(
                    "DM request crashed for queued comment %d/%d comment_id=%s username=%s",
                    index,
                    total,
                    comment_id,
                    username,
                )
                mark_failed(comment_id)
                failed += 1
                continue

            if not ok:
                logger.error(
                    "Skipping public reply for queued comment %d/%d because DM failed comment_id=%s username=%s response=%s",
                    index,
                    total,
                    comment_id,
                    username,
                    response,
                )

                mark_failed(comment_id)
                failed += 1
                continue

            mark_dm_sent(comment_id)

        try:
            reply_comment(comment_id)

            mark_done(comment_id)

            success += 1

            logger.info(
                "Completed queued comment %d/%d comment_id=%s username=%s",
                index,
                total,
                comment_id,
                username,
                extra={"highlight": "success"},
            )

        except Exception:
            logger.exception(
                "Public reply failed after DM success for queued comment %d/%d comment_id=%s username=%s",
                index,
                total,
                comment_id,
                username,
            )

            mark_failed(comment_id)

            failed += 1

        delay = random.uniform(*COMMENT_PROCESSING_DELAY_SECONDS)
        logger.info("Waiting %.1f seconds before processing next comment progress=%d/%d", delay, index, total)
        time.sleep(delay)

    logger.info("Processing summary success=%d failed=%d total=%d", success, failed, total, extra={"highlight": "summary"})
    clear_done()

def main():
    parser = argparse.ArgumentParser(
        description="Instagram comment automation"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True
    )

    discover_parser = subparsers.add_parser(
        "discover",
        help="Fetch latest comments and enqueue eligible ones"
    )

    discover_parser.add_argument(
        "media_name",
        choices=MEDIA.keys(),
        help="Media to discover comments from"
    )

    discover_parser.add_argument(
        "count",
        type=int,
        nargs="?",
        default=DISCOVER_DEFAULT,
        help="Number of comments to scan"
    )

    process_parser = subparsers.add_parser(
        "process",
        help="Process queued comments"
    )
    
    process_parser.add_argument(
        "media_name",
        choices=MEDIA.keys(),
        help="Media to process"
    )

    process_parser.add_argument(
        "count",
        type=int,
        nargs="?",
        default=PROCESS_DEFAULT,
        help="Number of queued comments to process"
    )

    media_parser = subparsers.add_parser(
        "media",
        help="List recent media"
    )

    args = parser.parse_args()

    if args.command == "discover":
        logger.info(
            "Starting discovery command count=%d",
            args.count,
            extra={"highlight": "start"},
        )
        discover(args.media_name, args.count)

    elif args.command == "process":
        logger.info(
            "Starting process command count=%d",
            args.count,
            extra={"highlight": "start"},
        )
        process(args.media_name, args.count)

    elif args.command == "media":
        media_list = list(get_media())

        with open("media.json", "w", encoding="utf-8") as f:
            json.dump(media_list, f, indent=4, ensure_ascii=False)

        print(f"Saved {len(media_list)} media items to media.json")

if __name__ == "__main__":
    main()
