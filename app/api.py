import time
import requests
from urllib.parse import urlsplit

from .config import ACCESS_TOKEN, BASE_URL, IG_USER_ID
from .logger import OUT_ACCESS_LOGGER, format_log_body, logger

REQUEST_TIMEOUT = 30


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


def _request(method, url, *, params=None, data=None, json=None, headers=None):
    started_at = time.perf_counter()
    method_upper = method.upper()
    path = urlsplit(url).path
    request_body = json if json is not None else data

    try:
        response = requests.request(
            method,
            url,
            params=params,
            data=data,
            json=json,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
        OUT_ACCESS_LOGGER.exception(
            "OUTBOUND request method=%s path=%s status=error duration_ms=%s request_body=%s response_body=%s",
            method_upper,
            path,
            duration_ms,
            format_log_body(request_body),
            "-",
        )
        raise

    duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
    OUT_ACCESS_LOGGER.info(
        "OUTBOUND request method=%s path=%s status=%s duration_ms=%s request_body=%s response_body=%s",
        method_upper,
        path,
        response.status_code,
        duration_ms,
        format_log_body(request_body),
        format_log_body(_response_body(response)),
    )

    return response


def get_comments(media_id: str, limit: int | None):
    url = f"{BASE_URL}/{media_id}/comments"

    params = {
        "fields": "id,text,username,from,parent_id,hidden,timestamp",
        "access_token": ACCESS_TOKEN,
        "limit": min(limit, 500) if limit is not None else 500,
    }

    remaining = limit
    page = 1

    while url and (remaining is None or remaining > 0):
        logger.debug(
            "Fetching comments page=%d remaining=%s media_id=%s",
            page,
            remaining if remaining is not None else "all",
            media_id,
        )

        response = _request("GET", url, params=params)

        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.exception(
                "Failed to fetch comments page=%d media_id=%s status=%s body=%s",
                page,
                media_id,
                response.status_code,
                _response_body(response),
            )
            raise

        data = response.json()
        comments = data.get("data", [])

        for comment in comments:
            yield comment

            if remaining is not None:
                remaining -= 1

                if remaining == 0:
                    break

        url = data.get("paging", {}).get("next")
        params = None
        page += 1


def reply_comment(comment_id: str, message: str):
    response = _request(
        "POST",
        f"{BASE_URL}/{comment_id}/replies",
        data={
            "message": message,
            "access_token": ACCESS_TOKEN,
        },
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


def send_dm(comment_id: str, message: str):
    response = _request(
        "POST",
        f"{BASE_URL}/{IG_USER_ID}/messages",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "recipient": {
                "comment_id": comment_id,
            },
            "message": {
                "text": message,
            },
        },
    )

    if response.status_code == 200:
        logger.info(
            "DM sent comment_id=%s status=%s response=%s",
            comment_id,
            response.status_code,
            _response_body(response),
        )
        return True, None

    error = {
        "status_code": response.status_code,
        "message": _error_message(response),
        "body": _response_body(response),
    }

    logger.error(
        "DM failed comment_id=%s error=%s",
        comment_id,
        error,
    )
    return False, error


def get_media(stop_ids=None):
    url = f"{BASE_URL}/{IG_USER_ID}/media"
    stop_ids = set(stop_ids or [])

    params = {
        "fields": "id,caption,comments_count,media_type,media_product_type,timestamp",
        "access_token": ACCESS_TOKEN,
    }

    while url:
        response = _request("GET", url, params=params)
        response.raise_for_status()

        data = response.json()

        for media in data.get("data", []):
            if media.get("id") in stop_ids:
                return
            yield media

        url = data.get("paging", {}).get("next")
        params = None


def get_media_insights(media_id: str, metrics):
    url = f"{BASE_URL}/{media_id}/insights"

    params = {
        "metric": ",".join(metrics),
        "access_token": ACCESS_TOKEN,
    }

    logger.info(
        "Fetching insights media_id=%s metrics=%s",
        media_id,
        ",".join(metrics),
    )

    response = _request("GET", url, params=params)

    if response.status_code >= 400:
        logger.error(
            "Failed to fetch insights media_id=%s status=%s body=%s",
            media_id,
            response.status_code,
            _response_body(response),
        )
        response.raise_for_status()

    return response.json()


def get_media_by_id(media_id: str):
    response = _request(
        "GET",
        f"{BASE_URL}/{media_id}",
        params={
            "fields": "id,caption,comments_count,media_type,media_product_type,timestamp",
            "access_token": ACCESS_TOKEN,
        },
    )

    try:
        response.raise_for_status()
    except requests.HTTPError:
        logger.exception(
            "Failed to fetch media media_id=%s status=%s body=%s",
            media_id,
            response.status_code,
            _response_body(response),
        )
        raise

    return response.json()
