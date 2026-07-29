import requests
from config import ACCESS_TOKEN, BASE_URL, DM_MESSAGES, IG_USER_ID, MEDIA, MY_USERNAME
import itertools
from logger import logger
import random

REPLIES = [
    "Please check DM",
    "Please check your DM",
    "Shared the location in DM",
    "I've sent you the location in DM",
    "Location sent! Check your DM",
    "sent you the location",
    "a must visit place"
]
reply_cycle = itertools.cycle(REPLIES)

def get_dm_message(media_name):
    template = random.choice(DM_MESSAGES)
    return template.format(
        location=MEDIA[media_name]["location"]
    )

def _response_body(response):
    try:
        return response.json()
    except ValueError:
        return response.text

def _error_message(response):
    body = _response_body(response)

    if isinstance(body, dict):
        return body.get("error", {}).get("message") or body.get("message") or body

    return body

def _safe_url(url):
    if not ACCESS_TOKEN:
        return url

    return url.replace(ACCESS_TOKEN, "<redacted>")

def get_comments(media_id: str, limit: int):
    url = f"{BASE_URL}/{media_id}/comments"

    params = {
        "fields": "id,text,username,from,parent_id,hidden,timestamp",
        "access_token": ACCESS_TOKEN,
        "limit": limit > 500 and 500 or limit
    }

    remaining = limit
    page = 1

    logger.info("Fetching up to %d comments for media_id=%s", limit, media_id)

    while url and remaining > 0:
        logger.debug("Requesting comments page=%d remaining=%d url=%s", page, remaining, _safe_url(url))

        response = requests.get(url, params=params, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.exception(
                "Failed to fetch comments page=%d status=%s body=%s",
                page,
                response.status_code,
                _response_body(response),
            )
            raise

        data = response.json()
        comments = data.get("data", [])
        logger.info("Fetched comments page=%d count=%d remaining_before_page=%d", page, len(comments), remaining)

        for comment in comments:
            yield comment
            remaining -= 1

            if remaining == 0:
                break

        url = data.get("paging", {}).get("next")
        params = None
        page += 1

    logger.info("Finished fetching comments requested=%d remaining=%d", limit, remaining)

def should_reply(text):

    text = text.lower()

    keywords = [
        "location",
        "loc",
        "link",
        "map",
        "maps",
        "place",
        "where",
        "details",
        "📍"
    ]

    return any(k in text for k in keywords)

def reply_comment(comment_id):
    message = next(reply_cycle)
    logger.info("Posting public reply comment_id=%s", comment_id)

    response = requests.post(
        f"{BASE_URL}/{comment_id}/replies",
        data={
            "message": message,
            "access_token": ACCESS_TOKEN
        },
        timeout=30
    )

    try:
        response.raise_for_status()
    except requests.HTTPError:
        logger.exception(
            "Public reply failed comment_id=%s status=%s body=%s",
            comment_id,
            response.status_code,
            _response_body(response),
        )
        raise

    logger.info(
        "Public reply posted comment_id=%s status=%s response=%s",
        comment_id,
        response.status_code,
        _response_body(response),
    )

def _dm_error(response):
    body = _response_body(response)
    return {
        "status_code": response.status_code,
        "message": _error_message(response),
        "body": body,
    }

def send_dm(comment_id, media_name):
    logger.info("Sending DM for media_name=%s comment_id=%s ig_user_id=%s", media_name, comment_id, IG_USER_ID)

    response = requests.post(
        f"{BASE_URL}/{IG_USER_ID}/messages",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "recipient": {
                "comment_id": comment_id
            },
            "message": {
                "text": get_dm_message(media_name)
            }
        },
        timeout=30
    )

    if response.status_code == 200:
        logger.info(
            "DM sent comment_id=%s status=%s response=%s",
            comment_id,
            response.status_code,
            _response_body(response),
        )
        return True, None

    error = _dm_error(response)
    logger.error("DM failed comment_id=%s error=%s", comment_id, error)
    return False, error

def get_media():
    url = f"{BASE_URL}/{IG_USER_ID}/media"

    params = {
        "fields": "id,caption,comments_count",
        "access_token": ACCESS_TOKEN,
    }

    while url:
        response = requests.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        for media in data.get("data", []):
            yield media

        paging = data.get("paging", {})
        url = paging.get("next")
        params = None  # next already contains the access token & cursor