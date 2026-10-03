import random

from app import api
from app.config import DM_MESSAGES, get_media_config
from app.logger import logger


def get_dm_message(media_name):
    template = random.choice(DM_MESSAGES)
    return template.format(
        location=get_media_config(media_name)["location"]
    )


def get_comments(media_id: str, limit: int | None):
    logger.info(
        "Fetching comments for media_id=%s limit=%s",
        media_id,
        limit if limit is not None else "all",
    )
    yield from api.get_comments(media_id, limit)


def should_reply(text):
    text = text.lower()

    keywords = [
        "location",
        "loc",
        "link",
        "map",
        "maps",
        "which place",
        "where",
        "details",
        "📍",
    ]

    return any(k in text for k in keywords)


PUBLIC_REPLY_MESSAGE = "Please check DM"


def reply_comment(comment_id):
    logger.info(
        "Posting public reply comment_id=%s",
        comment_id,
    )

    api.reply_comment(comment_id, PUBLIC_REPLY_MESSAGE)


def send_dm(comment_id, media_name):
    message = get_dm_message(media_name)

    logger.info(
        "Sending DM for media_name=%s comment_id=%s",
        media_name,
        comment_id,
    )

    return api.send_dm(comment_id, message)
