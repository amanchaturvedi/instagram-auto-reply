import itertools
import random

from app import api
from app.config import DM_MESSAGES, MEDIA, MY_USERNAME
from app.logger import logger

REPLIES = [
    "Please check DM",
    "Please check your DM",
    "Shared the location in DM",
    "I've sent you the location in DM",
    "Location sent! Check your DM",
    "Sent you the location",
]

reply_cycle = itertools.cycle(REPLIES)


def get_dm_message(media_name):
    template = random.choice(DM_MESSAGES)
    return template.format(
        location=MEDIA[media_name]["location"]
    )


def get_comments(media_id: str, limit: int):
    logger.info(
        "Fetching up to %d comments for media_id=%s",
        limit,
        media_id,
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


def reply_comment(comment_id):
    message = next(reply_cycle)

    logger.info(
        "Posting public reply comment_id=%s",
        comment_id,
    )

    api.reply_comment(comment_id, message)


def send_dm(comment_id, media_name):
    message = get_dm_message(media_name)

    logger.info(
        "Sending DM for media_name=%s comment_id=%s",
        media_name,
        comment_id,
    )

    return api.send_dm(comment_id, message)
